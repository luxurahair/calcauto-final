from fastapi import APIRouter, HTTPException, Header
from typing import Optional, List
from datetime import datetime, timedelta
from database import db, SMTP_EMAIL, logger
from models import Submission, SubmissionCreate, ReminderUpdate
from dependencies import get_current_user, calculate_monthly_payment

router = APIRouter()

from services.email_service import send_email

# ============ CRM Endpoints ============

@router.post("/submissions")
async def create_submission(submission: SubmissionCreate, authorization: Optional[str] = Header(None)):
    """Créer une nouvelle soumission avec rappel automatique 24h"""
    from datetime import timedelta
    
    user = await get_current_user(authorization)
    
    # Set default reminder to 24h from now
    reminder_date = datetime.utcnow() + timedelta(hours=24)
    
    new_submission = Submission(
        client_name=submission.client_name,
        client_phone=submission.client_phone,
        client_email=submission.client_email,
        vehicle_brand=submission.vehicle_brand,
        vehicle_model=submission.vehicle_model,
        vehicle_year=submission.vehicle_year,
        vehicle_price=submission.vehicle_price,
        term=submission.term,
        payment_monthly=submission.payment_monthly,
        payment_biweekly=submission.payment_biweekly,
        payment_weekly=submission.payment_weekly,
        selected_option=submission.selected_option,
        rate=submission.rate,
        program_month=submission.program_month,
        program_year=submission.program_year,
        reminder_date=reminder_date,
        owner_id=user["id"],
        calculator_state=submission.calculator_state
    )
    
    await db.submissions.insert_one(new_submission.dict())
    
    return {"success": True, "submission": new_submission.dict(), "message": "Soumission enregistrée - Rappel dans 24h"}

@router.get("/submissions")
async def get_submissions(search: Optional[str] = None, status: Optional[str] = None, authorization: Optional[str] = Header(None)):
    """Récupérer les soumissions de l'utilisateur connecté"""
    user = await get_current_user(authorization)
    
    query = {"owner_id": user["id"]}
    
    if search:
        # Search by name or phone
        query["$or"] = [
            {"client_name": {"$regex": search, "$options": "i"}},
            {"client_phone": {"$regex": search, "$options": "i"}}
        ]
    
    if status:
        query["status"] = status
    
    submissions = await db.submissions.find(query).sort("submission_date", -1).to_list(500)
    
    # Convert ObjectId to string and datetime to ISO format
    for sub in submissions:
        if "_id" in sub:
            sub["_id"] = str(sub["_id"])
        if "submission_date" in sub and sub["submission_date"]:
            sub["submission_date"] = sub["submission_date"].isoformat()
        if "reminder_date" in sub and sub["reminder_date"]:
            sub["reminder_date"] = sub["reminder_date"].isoformat()
    
    return submissions

@router.get("/submissions/reminders")
async def get_reminders(authorization: Optional[str] = Header(None)):
    """Récupérer les soumissions avec rappels dus ou à venir pour l'utilisateur connecté"""
    user = await get_current_user(authorization)
    now = datetime.utcnow()
    
    # Get submissions where reminder is due and not done (filtré par owner_id)
    reminders_due = await db.submissions.find({
        "owner_id": user["id"],
        "reminder_done": False,
        "reminder_date": {"$lte": now}
    }).sort("reminder_date", 1).to_list(100)
    
    # Get upcoming reminders (next 7 days)
    from datetime import timedelta
    next_week = now + timedelta(days=7)
    
    reminders_upcoming = await db.submissions.find({
        "owner_id": user["id"],
        "reminder_done": False,
        "reminder_date": {"$gt": now, "$lte": next_week}
    }).sort("reminder_date", 1).to_list(100)
    
    # Format dates
    for sub in reminders_due + reminders_upcoming:
        if "_id" in sub:
            sub["_id"] = str(sub["_id"])
        if "submission_date" in sub and sub["submission_date"]:
            sub["submission_date"] = sub["submission_date"].isoformat()
        if "reminder_date" in sub and sub["reminder_date"]:
            sub["reminder_date"] = sub["reminder_date"].isoformat()
    
    return {
        "due": reminders_due,
        "upcoming": reminders_upcoming,
        "due_count": len(reminders_due),
        "upcoming_count": len(reminders_upcoming)
    }

@router.put("/submissions/{submission_id}/reminder")
async def update_reminder(submission_id: str, reminder: ReminderUpdate, authorization: Optional[str] = Header(None)):
    """Mettre à jour la date de rappel"""
    user = await get_current_user(authorization)
    
    update_data = {"reminder_date": reminder.reminder_date, "reminder_done": False}
    
    if reminder.notes:
        update_data["notes"] = reminder.notes
    
    result = await db.submissions.update_one(
        {"id": submission_id, "owner_id": user["id"]},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")
    
    return {"success": True, "message": "Rappel mis à jour"}

@router.put("/submissions/{submission_id}/done")
async def mark_reminder_done(submission_id: str, authorization: Optional[str] = Header(None), new_reminder_date: Optional[str] = None):
    """Marquer un rappel comme fait, optionnellement planifier un nouveau"""
    user = await get_current_user(authorization)
    
    update_data = {"reminder_done": True, "status": "contacted"}
    
    if new_reminder_date:
        update_data["reminder_date"] = datetime.fromisoformat(new_reminder_date.replace('Z', '+00:00'))
        update_data["reminder_done"] = False
    
    result = await db.submissions.update_one(
        {"id": submission_id, "owner_id": user["id"]},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")
    
    return {"success": True, "message": "Rappel marqué comme fait" + (" - Nouveau rappel planifié" if new_reminder_date else "")}

@router.put("/submissions/{submission_id}/status")
async def update_submission_status(submission_id: str, status: str, authorization: Optional[str] = Header(None)):
    """Mettre à jour le statut (pending, contacted, converted, lost)"""
    user = await get_current_user(authorization)
    
    if status not in ["pending", "contacted", "converted", "lost"]:
        raise HTTPException(status_code=400, detail="Statut invalide")
    
    result = await db.submissions.update_one(
        {"id": submission_id, "owner_id": user["id"]},
        {"$set": {"status": status}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")
    
    return {"success": True, "message": f"Statut mis à jour: {status}"}

@router.delete("/submissions/{submission_id}/reminder")
async def delete_reminder(submission_id: str, authorization: Optional[str] = Header(None)):
    """Supprimer un rappel (remet reminder_date à null et reminder_done à true)"""
    user = await get_current_user(authorization)
    
    result = await db.submissions.update_one(
        {"id": submission_id, "owner_id": user["id"]},
        {"$set": {"reminder_date": None, "reminder_done": True}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")
    
    return {"success": True, "message": "Rappel supprimé"}

@router.delete("/submissions/{submission_id}")
async def delete_submission(submission_id: str, authorization: Optional[str] = Header(None)):
    """Supprimer une soumission/offre complètement"""
    user = await get_current_user(authorization)
    
    result = await db.submissions.delete_one({
        "id": submission_id,
        "owner_id": user["id"]
    })
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Soumission non trouvée")
    
    return {"success": True, "message": "Soumission supprimée"}

@router.delete("/contacts/{contact_id}/history")
async def delete_contact_history(contact_id: str, authorization: Optional[str] = Header(None)):
    """Supprimer tout l'historique (soumissions) d'un contact"""
    user = await get_current_user(authorization)
    
    # Vérifier que le contact existe et appartient à l'utilisateur
    contact = await db.contacts.find_one({
        "id": contact_id,
        "owner_id": user["id"]
    })
    
    if not contact:
        raise HTTPException(status_code=404, detail="Contact non trouvé")
    
    # Supprimer toutes les soumissions liées à ce contact
    result = await db.submissions.delete_many({
        "contact_id": contact_id,
        "owner_id": user["id"]
    })
    
    return {
        "success": True, 
        "message": f"Historique supprimé ({result.deleted_count} soumissions)"
    }

@router.delete("/better-offers/{submission_id}")
async def delete_better_offer(submission_id: str, authorization: Optional[str] = Header(None)):
    """Supprimer une offre améliorée de la liste"""
    user = await get_current_user(authorization)
    
    # Marquer l'offre comme ignorée (équivalent à suppression de la liste)
    result = await db.submissions.update_one(
        {"id": submission_id, "owner_id": user["id"]},
        {"$set": {"better_offer_status": "deleted"}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    return {"success": True, "message": "Offre supprimée de la liste"}

def _calc_payment(principal: float, annual_rate: float, term_months: int) -> float:
    """Helper: calcul paiement mensuel"""
    if principal <= 0:
        return 0.0
    if annual_rate == 0:
        return round(principal / term_months, 2)
    mr = annual_rate / 100 / 12
    return round(principal * (mr * (1 + mr) ** term_months) / ((1 + mr) ** term_months - 1), 2)

@router.post("/compare-programs")
async def compare_programs_with_submissions(authorization: Optional[str] = Header(None)):
    """Compare les programmes actuels avec les soumissions passées pour trouver de meilleures offres"""
    user = await get_current_user(authorization)
    
    try:
        latest = await db.programs.find_one(sort=[("program_year", -1), ("program_month", -1)])
        if not latest:
            return {"better_offers": [], "count": 0}
        
        current_month = latest["program_month"]
        current_year = latest["program_year"]
        
        submissions = await db.submissions.find({
            "owner_id": user["id"],
            "$or": [
                {"program_month": {"$lt": current_month}, "program_year": current_year},
                {"program_year": {"$lt": current_year}}
            ]
        }).to_list(500)
        
        better_offers = []
        all_terms = [36, 48, 60, 72, 84, 96]
        
        for sub in submissions:
            program = await db.programs.find_one({
                "brand": sub.get("vehicle_brand"),
                "model": sub.get("vehicle_model"),
                "year": sub.get("vehicle_year"),
                "program_month": current_month,
                "program_year": current_year
            })
            
            if not program:
                continue
            
            term = int(sub.get("term", 72))
            old_payment = float(sub.get("payment_monthly", 0))
            vehicle_price = float(sub.get("vehicle_price", 0))
            consumer_cash = float(program.get("consumer_cash", 0))
            bonus_cash = float(program.get("bonus_cash", 0))
            alt_cc = float(program.get("alternative_consumer_cash", program.get("alt_consumer_cash", 0)) or 0)
            opt1_rates = program.get("option1_rates", {})
            opt2_rates = program.get("option2_rates")
            
            # Calculate new Option 1 payment for the client's term
            rate_key = f"rate_{term}"
            new_rate = float(opt1_rates.get(rate_key, 4.99))
            opt1_principal = vehicle_price - consumer_cash - bonus_cash
            
            if opt1_principal <= 0:
                continue
            
            new_payment = _calc_payment(opt1_principal, new_rate, term)
            
            if new_payment >= old_payment - 10:
                continue
            
            savings_monthly = round(old_payment - new_payment, 2)
            savings_total = round(savings_monthly * term, 2)
            
            # Pre-calculate payments for ALL terms, both options
            payments_by_term = {}
            for t in all_terms:
                rk = f"rate_{t}"
                o1_rate = float(opt1_rates.get(rk, 0))
                o1_pay = _calc_payment(opt1_principal, o1_rate, t)
                
                o2_rate = None
                o2_pay = None
                if opt2_rates:
                    o2_rate = float(opt2_rates.get(rk, 0))
                    o2_principal = vehicle_price - alt_cc - bonus_cash
                    o2_pay = _calc_payment(o2_principal, o2_rate, t)
                
                payments_by_term[str(t)] = {
                    "opt1_rate": round(o1_rate, 2),
                    "opt1_payment": o1_pay,
                    "opt2_rate": round(o2_rate, 2) if o2_rate is not None else None,
                    "opt2_payment": o2_pay,
                }
            
            better_offers.append({
                "submission_id": str(sub.get("id", "")),
                "owner_id": user["id"],
                "client_name": str(sub.get("client_name", "")),
                "client_phone": str(sub.get("client_phone", "")),
                "client_email": str(sub.get("client_email", "")),
                "vehicle": f"{sub.get('vehicle_brand', '')} {sub.get('vehicle_model', '')} {sub.get('vehicle_year', '')}",
                "vehicle_brand": str(sub.get("vehicle_brand", "")),
                "vehicle_model": str(sub.get("vehicle_model", "")),
                "vehicle_year": int(sub.get("vehicle_year", 0)),
                "vehicle_price": round(vehicle_price, 2),
                "old_payment": round(old_payment, 2),
                "new_payment": round(new_payment, 2),
                "old_rate": round(float(sub.get("rate", 0)), 2),
                "new_rate": round(new_rate, 2),
                "old_consumer_cash": round(float(sub.get("calculator_state", {}).get("selectedProgram", {}).get("consumer_cash", 0)) if isinstance(sub.get("calculator_state"), dict) else 0, 2),
                "new_consumer_cash": round(consumer_cash, 2),
                "savings_monthly": round(savings_monthly, 2),
                "savings_total": round(savings_total, 2),
                "term": term,
                "old_program": f"{sub.get('program_month', '?')}/{sub.get('program_year', '?')}",
                "new_program": f"{current_month}/{current_year}",
                "old_selected_option": str(sub.get("selected_option", "1")),
                "approved": False,
                "email_sent": False,
                "calculator_state": sub.get("calculator_state") if isinstance(sub.get("calculator_state"), dict) else None,
                "new_program_data": {
                    "consumer_cash": round(consumer_cash, 2),
                    "bonus_cash": round(bonus_cash, 2),
                    "alt_consumer_cash": round(alt_cc, 2),
                    "option1_rates": opt1_rates,
                    "option2_rates": opt2_rates,
                },
                "payments_by_term": payments_by_term,
            })
        
        if better_offers:
            await db.better_offers.delete_many({"owner_id": user["id"]})
            for offer in better_offers:
                await db.better_offers.insert_one(offer.copy())
            
            try:
                send_better_offers_notification(better_offers)
            except Exception as e:
                logger.error(f"Error sending better offers notification: {e}")
        
        return {"better_offers": better_offers, "count": len(better_offers)}
    
    except Exception as e:
        logger.error(f"Error in compare_programs: {e}")
        return {"better_offers": [], "count": 0, "error": str(e)}

def send_better_offers_notification(offers: List[dict]):
    """Envoie une notification par email des meilleures offres disponibles"""
    if not SMTP_EMAIL:
        return
    
    offers_html = ""
    for offer in offers:
        offers_html += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">{offer['client_name']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee;">{offer['vehicle']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right;">{offer['old_payment']:.2f}$</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right; color: #28a745; font-weight: bold;">{offer['new_payment']:.2f}$</td>
            <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: right; color: #28a745;">-{offer['savings_monthly']:.2f}$/mois</td>
        </tr>
        """
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5;">
        <div style="max-width: 700px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden;">
            <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0;">🔔 Meilleures Offres Disponibles</h1>
            </div>
            <div style="padding: 20px;">
                <p style="font-size: 16px;">{len(offers)} client(s) peuvent bénéficier de meilleurs taux!</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background: #f8f9fa;">
                        <th style="padding: 12px; text-align: left;">Client</th>
                        <th style="padding: 12px; text-align: left;">Véhicule</th>
                        <th style="padding: 12px; text-align: right;">Ancien</th>
                        <th style="padding: 12px; text-align: right;">Nouveau</th>
                        <th style="padding: 12px; text-align: right;">Économie</th>
                    </tr>
                    {offers_html}
                </table>
                
                <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                    <strong>⚠️ Action requise:</strong><br>
                    Ouvrez l'application pour approuver l'envoi des emails aux clients.
                </div>
                
                <a href="https://deal-detail-modal.preview.emergentagent.com" style="display: inline-block; background: #4ECDC4; color: #1a1a2e; padding: 12px 24px; border-radius: 8px; text-decoration: none; font-weight: bold;">
                    Ouvrir l'application
                </a>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(SMTP_EMAIL, f"🔔 CalcAuto - {len(offers)} client(s) à relancer!", html_body)

@router.get("/better-offers")
async def get_better_offers(authorization: Optional[str] = Header(None)):
    """Récupérer les meilleures offres en attente d'approbation pour l'utilisateur connecté"""
    user = await get_current_user(authorization)
    
    offers = await db.better_offers.find({
        "owner_id": user["id"],
        "approved": False, 
        "email_sent": False
    }).to_list(100)
    
    for offer in offers:
        if "_id" in offer:
            offer["_id"] = str(offer["_id"])
    
    return offers

@router.post("/better-offers/{submission_id}/approve")
async def approve_better_offer(submission_id: str, authorization: Optional[str] = Header(None)):
    """Approuver et envoyer l'email au client pour une meilleure offre"""
    user = await get_current_user(authorization)
    
    offer = await db.better_offers.find_one({"submission_id": submission_id, "owner_id": user["id"]})
    
    if not offer:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    if offer.get("email_sent"):
        return {"success": False, "message": "Email déjà envoyé"}
    
    # Send email to client
    try:
        send_client_better_offer_email(offer)
        
        # Mark as sent
        await db.better_offers.update_one(
            {"submission_id": submission_id, "owner_id": user["id"]},
            {"$set": {"approved": True, "email_sent": True}}
        )
        
        return {"success": True, "message": f"Email envoyé à {offer['client_email']}"}
    except Exception as e:
        logger.error(f"Error sending client email: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur d'envoi: {str(e)}")

def send_client_better_offer_email(offer: dict):
    """Envoie un email au client pour l'informer d'une meilleure offre"""
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; padding: 20px; background: #f5f5f5;">
        <div style="max-width: 600px; margin: 0 auto; background: white; border-radius: 10px; overflow: hidden;">
            <div style="background: #1a1a2e; color: white; padding: 20px; text-align: center;">
                <h1 style="margin: 0; color: #4ECDC4;">🎉 Bonne Nouvelle!</h1>
            </div>
            <div style="padding: 30px;">
                <p style="font-size: 18px;">Bonjour {offer['client_name']},</p>
                
                <p>De nouveaux programmes de financement sont disponibles et vous permettraient d'<strong>économiser</strong> sur votre {offer['vehicle']}!</p>
                
                <div style="background: #d4edda; border-radius: 10px; padding: 20px; margin: 20px 0; text-align: center;">
                    <p style="margin: 0; color: #666;">Votre paiement actuel</p>
                    <p style="font-size: 24px; margin: 5px 0; text-decoration: line-through; color: #999;">{offer['old_payment']:.2f}$/mois</p>
                    
                    <p style="margin: 15px 0 0; color: #666;">Nouveau paiement possible</p>
                    <p style="font-size: 32px; margin: 5px 0; color: #28a745; font-weight: bold;">{offer['new_payment']:.2f}$/mois</p>
                    
                    <p style="font-size: 18px; color: #28a745; margin-top: 15px;">
                        💰 Économie: {offer['savings_monthly']:.2f}$/mois ({offer['savings_total']:.2f}$ sur {offer['term']} mois)
                    </p>
                </div>
                
                <p>Contactez-nous pour profiter de cette offre!</p>
                
                <p style="color: #666; font-size: 14px; margin-top: 30px;">
                    Cordialement,<br>
                    L'équipe CalcAuto AiPro
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    send_email(offer['client_email'], f"🎉 Économisez {offer['savings_monthly']:.2f}$/mois sur votre {offer['vehicle']}!", html_body)

@router.post("/better-offers/{submission_id}/ignore")
async def ignore_better_offer(submission_id: str, authorization: Optional[str] = Header(None)):
    """Ignorer une meilleure offre"""
    user = await get_current_user(authorization)
    
    result = await db.better_offers.delete_one({"submission_id": submission_id, "owner_id": user["id"]})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Offre non trouvée")
    
    return {"success": True, "message": "Offre ignorée"}

