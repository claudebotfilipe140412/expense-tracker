#!/usr/bin/env python3
"""
Expense Tracker Dashboard - Track monthly income, expenses, and savings
"""
import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

import splitwise_sync

app = FastAPI(title="Expense Tracker")

# Setup
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

DB_PATH = Path(__file__).parent / "expenses.db"

# ============ CONFIGURATION ============
CONFIG = {
    "income": 2851.74,
    "currency": "€",
    "fixed_expenses": [
        {"name": "Rent", "amount": 359.00, "category": "Housing"},
        {"name": "Gym", "amount": 32.40, "category": "Health & Fitness"},
        {"name": "Internet", "amount": 5.00, "category": "Utilities"},
        {"name": "Health Insurance", "amount": 80.16, "category": "Healthcare"},
    ],
    "savings": [
        {"name": "Savings Account", "amount": 500.00},
        {"name": "Retirement Plan", "amount": 50.00},
        {"name": "Investments", "amount": 1000.00},
    ],
    "categories": [
        "Food & Groceries",
        "Transportation",
        "Entertainment",
        "Shopping",
        "Utilities",
        "Healthcare",
        "Health & Fitness",
        "Housing",
        "Personal Care",
        "Education",
        "Travel",
        "Subscriptions",
        "Other",
    ],
}

# ============ DATABASE ============
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                is_fixed BOOLEAN DEFAULT FALSE,
                splitwise_id INTEGER UNIQUE,
                source TEXT DEFAULT 'manual',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Add columns if they don't exist (migration)
        try:
            conn.execute("ALTER TABLE expenses ADD COLUMN splitwise_id INTEGER UNIQUE")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE expenses ADD COLUMN source TEXT DEFAULT 'manual'")
        except sqlite3.OperationalError:
            pass
        
        # Settings table for Splitwise group
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        conn.commit()


init_db()


# ============ MODELS ============
class ExpenseCreate(BaseModel):
    date: str
    description: str
    amount: float
    category: str


class ExpenseResponse(BaseModel):
    id: int
    date: str
    description: str
    amount: float
    category: str
    is_fixed: bool


# ============ HELPERS ============
def get_month_expenses(year: int, month: int) -> list:
    """Get all expenses for a specific month."""
    with get_db() as conn:
        cursor = conn.execute(
            """
            SELECT * FROM expenses 
            WHERE strftime('%Y', date) = ? AND strftime('%m', date) = ?
            ORDER BY date DESC, id DESC
            """,
            (str(year), f"{month:02d}")
        )
        return [dict(row) for row in cursor.fetchall()]


def get_month_summary(year: int, month: int) -> dict:
    """Calculate monthly summary."""
    expenses = get_month_expenses(year, month)
    
    # Calculate totals
    total_fixed = sum(e["amount"] for e in CONFIG["fixed_expenses"])
    total_savings = sum(s["amount"] for s in CONFIG["savings"])
    total_variable = sum(e["amount"] for e in expenses)
    total_spent = total_fixed + total_variable
    
    # Available budget (income - fixed - savings)
    available_budget = CONFIG["income"] - total_fixed - total_savings
    remaining = available_budget - total_variable
    
    # Days in month calculation
    today = date.today()
    if year == today.year and month == today.month:
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        days_left = days_in_month - today.day + 1
        daily_budget = remaining / days_left if days_left > 0 else 0
    else:
        days_left = 0
        daily_budget = 0
    
    # Category breakdown
    category_totals = {}
    for expense in expenses:
        cat = expense["category"]
        category_totals[cat] = category_totals.get(cat, 0) + expense["amount"]
    
    return {
        "income": CONFIG["income"],
        "total_fixed": total_fixed,
        "total_savings": total_savings,
        "total_variable": total_variable,
        "total_spent": total_spent,
        "available_budget": available_budget,
        "remaining": remaining,
        "days_left": days_left,
        "daily_budget": daily_budget,
        "category_totals": category_totals,
        "expenses": expenses,
        "fixed_expenses": CONFIG["fixed_expenses"],
        "savings": CONFIG["savings"],
        "savings_rate": (total_savings / CONFIG["income"]) * 100,
    }


def get_available_months() -> list:
    """Get list of months that have expenses."""
    with get_db() as conn:
        cursor = conn.execute("""
            SELECT DISTINCT strftime('%Y', date) as year, strftime('%m', date) as month
            FROM expenses
            ORDER BY year DESC, month DESC
        """)
        months = [(int(row["year"]), int(row["month"])) for row in cursor.fetchall()]
    
    # Always include current month
    today = date.today()
    current = (today.year, today.month)
    if current not in months:
        months.insert(0, current)
    
    return months


# ============ ROUTES ============
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, year: Optional[int] = None, month: Optional[int] = None):
    """Main dashboard page."""
    today = date.today()
    year = year or today.year
    month = month or today.month
    
    summary = get_month_summary(year, month)
    available_months = get_available_months()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "summary": summary,
        "year": year,
        "month": month,
        "month_name": date(year, month, 1).strftime("%B %Y"),
        "categories": CONFIG["categories"],
        "currency": CONFIG["currency"],
        "available_months": available_months,
        "is_current_month": year == today.year and month == today.month,
        "now": datetime.now().strftime("%Y-%m-%d %H:%M"),
    })


@app.post("/expense")
async def add_expense(
    date_str: str = Form(..., alias="date"),
    description: str = Form(...),
    amount: float = Form(...),
    category: str = Form(...)
):
    """Add a new expense via form."""
    with get_db() as conn:
        conn.execute(
            "INSERT INTO expenses (date, description, amount, category) VALUES (?, ?, ?, ?)",
            (date_str, description, amount, category)
        )
        conn.commit()
    
    # Redirect back to the month of the expense
    expense_date = datetime.strptime(date_str, "%Y-%m-%d")
    return RedirectResponse(
        url=f"/?year={expense_date.year}&month={expense_date.month}",
        status_code=303
    )


@app.post("/api/expense")
async def api_add_expense(expense: ExpenseCreate):
    """Add a new expense via API (for Mako)."""
    with get_db() as conn:
        cursor = conn.execute(
            "INSERT INTO expenses (date, description, amount, category) VALUES (?, ?, ?, ?)",
            (expense.date, expense.description, expense.amount, expense.category)
        )
        conn.commit()
        expense_id = cursor.lastrowid
    
    return {"status": "ok", "id": expense_id, "message": f"Added {CONFIG['currency']}{expense.amount:.2f} for {expense.description}"}


@app.delete("/api/expense/{expense_id}")
async def delete_expense(expense_id: int):
    """Delete an expense."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Expense not found")
    
    return {"status": "ok", "message": "Expense deleted"}


@app.get("/api/summary")
async def api_summary(year: Optional[int] = None, month: Optional[int] = None):
    """Get monthly summary via API."""
    today = date.today()
    year = year or today.year
    month = month or today.month
    return get_month_summary(year, month)


@app.get("/api/config")
async def api_config():
    """Get configuration."""
    return CONFIG


# ============ SPLITWISE ROUTES ============
@app.get("/splitwise/status")
async def splitwise_status():
    """Check Splitwise connection status."""
    connected = splitwise_sync.is_authenticated()
    groups = []
    selected_group = None
    
    if connected:
        groups = splitwise_sync.get_groups()
        with get_db() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = 'splitwise_group_id'")
            row = cursor.fetchone()
            if row:
                selected_group = int(row["value"])
    
    return {
        "connected": connected,
        "groups": groups,
        "selected_group": selected_group,
    }


@app.get("/splitwise/connect")
async def splitwise_connect():
    """Start Splitwise OAuth flow."""
    url = splitwise_sync.get_auth_url()
    return RedirectResponse(url=url)


@app.get("/splitwise/callback")
async def splitwise_callback(code: str = None, state: str = None, error: str = None):
    """Handle Splitwise OAuth callback."""
    if error:
        return RedirectResponse(url="/?error=splitwise_denied")
    
    if code and state:
        success = splitwise_sync.complete_auth(code, state)
        if success:
            return RedirectResponse(url="/?success=splitwise_connected")
    
    return RedirectResponse(url="/?error=splitwise_failed")


@app.post("/splitwise/group")
async def set_splitwise_group(group_id: int = Form(...)):
    """Set the Splitwise group to sync."""
    with get_db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('splitwise_group_id', ?)",
            (str(group_id),)
        )
        conn.commit()
    return RedirectResponse(url="/?success=group_saved", status_code=303)


@app.post("/splitwise/sync")
async def sync_splitwise():
    """Manually trigger Splitwise sync."""
    with get_db() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = 'splitwise_group_id'")
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No Splitwise group selected")
        
        group_id = int(row["value"])
        result = splitwise_sync.sync_group(group_id, conn)
    
    return result


@app.get("/api/splitwise/sync")
async def api_sync_splitwise():
    """API endpoint for cron sync."""
    if not splitwise_sync.is_authenticated():
        return {"status": "error", "message": "Not authenticated"}
    
    with get_db() as conn:
        cursor = conn.execute("SELECT value FROM settings WHERE key = 'splitwise_group_id'")
        row = cursor.fetchone()
        if not row:
            return {"status": "error", "message": "No group selected"}
        
        group_id = int(row["value"])
        result = splitwise_sync.sync_group(group_id, conn)
    
    return {"status": "ok", **result}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
