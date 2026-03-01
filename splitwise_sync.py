#!/usr/bin/env python3
"""
Splitwise integration for Expense Tracker
"""
import os
import json
from datetime import datetime
from pathlib import Path
from splitwise import Splitwise
from dotenv import load_dotenv

# Load environment
load_dotenv(Path(__file__).parent / ".env")

CONSUMER_KEY = os.getenv("SPLITWISE_CONSUMER_KEY")
CONSUMER_SECRET = os.getenv("SPLITWISE_CONSUMER_SECRET")
TOKENS_FILE = Path(__file__).parent / ".splitwise_tokens.json"

# Category mapping from Splitwise to our categories
CATEGORY_MAP = {
    "Food and drink": "Food & Groceries",
    "Groceries": "Food & Groceries",
    "Dining out": "Food & Groceries",
    "Restaurants": "Food & Groceries",
    "Liquor": "Food & Groceries",
    "Transportation": "Transportation",
    "Taxi": "Transportation",
    "Parking": "Transportation",
    "Car": "Transportation",
    "Gas/fuel": "Transportation",
    "Bus/train": "Transportation",
    "Entertainment": "Entertainment",
    "Games": "Entertainment",
    "Movies": "Entertainment",
    "Music": "Entertainment",
    "Sports": "Entertainment",
    "Shopping": "Shopping",
    "Clothing": "Shopping",
    "Electronics": "Shopping",
    "Furniture": "Shopping",
    "Household supplies": "Shopping",
    "Gifts": "Shopping",
    "Utilities": "Utilities",
    "Electricity": "Utilities",
    "Heat/gas": "Utilities",
    "Water": "Utilities",
    "TV/Phone/Internet": "Utilities",
    "Cleaning": "Housing",
    "Rent": "Housing",
    "Mortgage": "Housing",
    "Insurance": "Healthcare",
    "Medical expenses": "Healthcare",
    "Life": "Other",
    "Education": "Education",
    "Childcare": "Other",
    "Pets": "Other",
    "General": "Other",
    "Uncategorized": "Other",
}

# Portuguese keyword-based categorization (checked against description)
# Keywords are lowercase, checked with "in" against lowercase description
KEYWORD_CATEGORIES = {
    # Utilities / Internet
    "Utilities": ["digi", "vodafone", "nos", "meo", "internet", "wifi", "luz", "electricidade", "água", "agua", "gás", "gas", "edp", "galp", "endesa"],
    
    # Food & Groceries
    "Food & Groceries": ["supermercado", "mercado", "pingo doce", "continente", "lidl", "aldi", "minipreço", "minipreco", "intermarché", "intermarche", "auchan", "jumbo", "mercearia", "talho", "padaria", "frutaria", "peixaria", "groceries", "compras", "café", "cafe", "pastelaria", "restaurante", "jantar", "almoço", "almoco", "comida", "pizza", "burger", "mcdonald", "uber eats", "glovo", "bolt food"],
    
    # Transportation
    "Transportation": ["uber", "bolt", "táxi", "taxi", "gasolina", "gasóleo", "gasoleo", "combustível", "combustivel", "estacionamento", "parking", "portagem", "via verde", "comboio", "metro", "autocarro", "bus", "cp", "carris", "fertagus", "transtejo"],
    
    # Entertainment
    "Entertainment": ["cinema", "netflix", "spotify", "hbo", "disney", "prime video", "youtube", "gaming", "jogo", "bilhete", "concerto", "teatro", "museu", "bar", "discoteca", "festa"],
    
    # Healthcare
    "Healthcare": ["farmácia", "farmacia", "médico", "medico", "hospital", "clínica", "clinica", "dentista", "consulta", "saúde", "saude", "medicamento", "receita"],
    
    # Shopping
    "Shopping": ["zara", "h&m", "primark", "worten", "fnac", "ikea", "leroy merlin", "decathlon", "sport zone", "amazon", "aliexpress", "roupa", "sapatos", "electrónica", "electronica"],
    
    # Personal Care
    "Personal Care": ["cabeleireiro", "barbeiro", "manicure", "spa", "massagem", "beleza", "cosmético", "cosmetico", "perfumaria"],
    
    # Subscriptions
    "Subscriptions": ["mensalidade", "subscrição", "subscricao", "assinatura", "premium"],
    
    # Travel
    "Travel": ["hotel", "airbnb", "booking", "voo", "avião", "aviao", "ryanair", "tap", "easyjet", "viagem", "férias", "ferias", "aeroporto"],
    
    # Housing
    "Housing": ["renda", "rent", "condomínio", "condominio", "seguro casa", "mobília", "mobilia"],
}


def categorize_by_keywords(description: str) -> str:
    """Categorize expense based on Portuguese keywords in description."""
    desc_lower = description.lower()
    
    for category, keywords in KEYWORD_CATEGORIES.items():
        for keyword in keywords:
            if keyword in desc_lower:
                return category
    
    return None  # No match, use Splitwise category


def get_splitwise_client():
    """Get authenticated Splitwise client."""
    s = Splitwise(CONSUMER_KEY, CONSUMER_SECRET)
    
    if TOKENS_FILE.exists():
        with open(TOKENS_FILE) as f:
            tokens = json.load(f)
            s.setOAuth2AccessToken(tokens)
    
    return s


def save_tokens(tokens: dict):
    """Save OAuth tokens."""
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f)
    os.chmod(TOKENS_FILE, 0o600)


def is_authenticated() -> bool:
    """Check if we have valid tokens."""
    if not TOKENS_FILE.exists():
        return False
    try:
        s = get_splitwise_client()
        user = s.getCurrentUser()
        return user is not None
    except Exception:
        return False


def get_auth_url() -> str:
    """Get OAuth authorization URL."""
    s = Splitwise(CONSUMER_KEY, CONSUMER_SECRET)
    url, state = s.getOAuth2AuthorizeURL("http://localhost:5000/splitwise/callback")
    # Store state for verification
    state_file = Path(__file__).parent / ".splitwise_state"
    state_file.write_text(state)
    return url


def complete_auth(code: str, state: str) -> bool:
    """Complete OAuth flow with authorization code."""
    state_file = Path(__file__).parent / ".splitwise_state"
    
    # Verify state
    if state_file.exists():
        stored_state = state_file.read_text().strip()
        if stored_state != state:
            return False
        state_file.unlink()
    
    s = Splitwise(CONSUMER_KEY, CONSUMER_SECRET)
    tokens = s.getOAuth2AccessToken(code, "http://localhost:5000/splitwise/callback")
    save_tokens(tokens)
    return True


def get_groups() -> list:
    """Get all groups."""
    s = get_splitwise_client()
    groups = s.getGroups()
    return [{"id": g.getId(), "name": g.getName()} for g in groups]


def get_expenses_for_sync(group_id: int, since_date: str = None) -> list:
    """Get expenses from a group that we paid for."""
    s = get_splitwise_client()
    current_user = s.getCurrentUser()
    current_user_id = current_user.getId()
    
    # Get expenses
    expenses = s.getExpenses(group_id=group_id, dated_after=since_date, limit=100)
    
    result = []
    for exp in expenses:
        # Skip deleted expenses
        if exp.getDeletedAt():
            continue
        
        # Skip if not a normal expense (e.g., payment/settlement)
        if exp.getPayment():
            continue
            
        # Get our share
        users = exp.getUsers()
        our_share = 0
        we_paid = False
        
        for user in users:
            if user.getId() == current_user_id:
                # What we owe
                owed = user.getOwedShare()
                paid = user.getPaidShare()
                our_share = float(owed) if owed else 0
                we_paid = float(paid) > 0 if paid else False
                break
        
        # Only include if we have a share
        if our_share > 0:
            description = exp.getDescription()
            
            # First try keyword-based categorization (Portuguese)
            keyword_cat = categorize_by_keywords(description)
            
            if keyword_cat:
                mapped_cat = keyword_cat
            else:
                # Fall back to Splitwise category mapping
                category = exp.getCategory()
                cat_name = category.getName() if category else "Other"
                mapped_cat = CATEGORY_MAP.get(cat_name, "Other")
            
            result.append({
                "splitwise_id": exp.getId(),
                "date": exp.getDate()[:10],  # YYYY-MM-DD
                "description": description,
                "amount": our_share,
                "category": mapped_cat,
                "original_category": category.getName() if category else "Other",
                "we_paid": we_paid,
            })
    
    return result


def sync_group(group_id: int, db_conn, since_date: str = None) -> dict:
    """Sync expenses from a Splitwise group to the database."""
    expenses = get_expenses_for_sync(group_id, since_date)
    
    added = 0
    skipped = 0
    
    for exp in expenses:
        # Check if already imported
        cursor = db_conn.execute(
            "SELECT id FROM expenses WHERE splitwise_id = ?",
            (exp["splitwise_id"],)
        )
        if cursor.fetchone():
            skipped += 1
            continue
        
        # Insert
        db_conn.execute(
            """INSERT INTO expenses (date, description, amount, category, splitwise_id, source)
               VALUES (?, ?, ?, ?, ?, 'splitwise')""",
            (exp["date"], exp["description"], exp["amount"], exp["category"], exp["splitwise_id"])
        )
        added += 1
    
    db_conn.commit()
    return {"added": added, "skipped": skipped, "total": len(expenses)}


if __name__ == "__main__":
    # Test authentication
    if is_authenticated():
        print("✅ Authenticated!")
        groups = get_groups()
        print("Groups:", groups)
    else:
        print("❌ Not authenticated")
        print("Auth URL:", get_auth_url())
