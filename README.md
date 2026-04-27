# Playto Payout Engine

Cross-border payout infrastructure for Indian merchants collecting international payments.


## Backend
```bash
cd backend
py -3.11 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data
python manage.py runserver
```

## Celery Worker (new terminal)
```bash
cd backend
venv\Scripts\activate
celery -A config worker --loglevel=info --pool=solo
```

## Celery Beat (new terminal)
```bash
cd backend
venv\Scripts\activate
celery -A config beat --loglevel=info
```

## Frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```

Visit http://localhost:5173

## Seeded Merchants
| Merchant | Balance |
|---|---|
| Priya Design Studio | Rs.23,000 |
| Arjun Freelance Dev | Rs.40,000 |
| Mumbai Digital Agency | Rs.1,05,000 |

## Running Tests
```bash
cd backend
python manage.py test tests
```

## API Reference
- GET  /api/v1/merchants/
- GET  /api/v1/merchants/<id>/
- POST /api/v1/merchants/<id>/payouts/   (requires Idempotency-Key header)
- GET  /api/v1/merchants/<id>/payouts/list/
- GET  /api/v1/payouts/<id>/
