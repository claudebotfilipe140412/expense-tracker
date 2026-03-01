# 💰 Expense Tracker

A personal expense tracking dashboard built with FastAPI.

## Features

- 📊 **Monthly Overview** - Income, spending, savings at a glance
- 🏠 **Fixed Expenses** - Track rent, subscriptions, bills
- 💎 **Savings Tracking** - Monitor savings accounts, retirement, investments
- 📝 **Variable Expenses** - Add daily expenses via UI or API
- 📈 **Category Breakdown** - Visual spending by category
- 📅 **Monthly History** - View previous months

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

Dashboard at **http://localhost:5000**

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Dashboard |
| POST | `/expense` | Add expense (form) |
| POST | `/api/expense` | Add expense (JSON) |
| DELETE | `/api/expense/{id}` | Delete expense |
| GET | `/api/summary` | Get monthly summary |
| GET | `/api/config` | Get configuration |

### Add expense via API

```bash
curl -X POST http://localhost:5000/api/expense \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-03-01", "description": "Coffee", "amount": 3.50, "category": "Food & Groceries"}'
```

## Configuration

Edit `main.py` to update:
- Income
- Fixed expenses
- Savings allocations
- Categories

## License

MIT
