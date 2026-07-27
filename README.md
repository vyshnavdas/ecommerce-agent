# E-Commerce Agent

E-Commerce Agent is a Django e-commerce project whose central feature is a staff-only AI operations agent. Through a natural-language chat interface, staff can manage catalogue data, ask business questions, send emails, and schedule background work without navigating separate administrative screens.

## AI agent features

The protected agent interface is available at `/agent/` to authenticated staff users.

| Feature | What the agent can do |
| --- | --- |
| Product CRUD | Create products, update names/prices/stock/descriptions/sizes/featured status, and delete products after explicit confirmation. |
| Natural-language analytics | Answer sales, revenue, product-performance, and inventory questions using the store database. |
| Email operations | Send plain-text emails to customers or administrators. |
| Task scheduling | Create, list, and cancel recurring cron jobs and one-off clocked jobs. |
| Conversation context | Retain recent complete conversation turns before each model call. |

### Agent workflow

1. A staff member submits a request in the chat interface.
2. Recent conversation history is trimmed to retain relevant context.
3. The model decides whether to respond directly or invoke a tool.
4. A tool performs the requested product, analytics, email, or scheduling operation.
5. The tool result is returned to the model and displayed in chat.


### Example: run a two-hour offer on the lowest-selling product

A staff member can ask the agent:

> Run an offer on the lowest-selling product for 2 hours. Reduce its price by 20%.

The agent handles this as a short workflow:

1. It uses the analytics tool to identify the lowest-selling product and retrieve its SKU and current price.
2. It calculates the offer price and calls `update_product` to apply that lower price immediately.
3. It calls `schedule_task` with `agent.tasks.restore_product_price`, a clocked schedule of `in 2 hours`, and the SKU plus original price as task arguments.
4. Celery Beat dispatches the one-off task after two hours; the Celery worker restores the product's original price.

For example, if `SKU-123` costs `₹1,000`, the agent updates it to `₹800` now and schedules the restoration with:

```text
task_name: agent.tasks.restore_product_price
schedule_type: clocked
run_at: in 2 hours
task_args: '["SKU-123", 1000]'
```

This requires both the Celery worker and Celery Beat scheduler to be running.

## Storefront features

The customer-facing store provides:

- Product catalogue, size filtering, images, reviews, and stock display.
- Session-based and authenticated-user carts.
- Registration, login, and account order history.
- Stripe Checkout with shipping information and order records.
- Product review submission for signed-in users.

## Technology stack

| Area | Technology |
| --- | --- |
| Web application | Django 6, HTML, CSS, JavaScript |
| Database | PostgreSQL with Psycopg |
| Payments | Stripe Checkout |
| AI orchestration | LangChain and LangGraph |
| Models | Google Gemini and Groq-hosted SQL helper |
| Background work | Celery and django-celery-beat |
| Email | Django email backend |

## Prerequisites

- Python 3.12 or later.
- PostgreSQL, running locally or available through a connection string.
- A Google API key for the Gemini agent.
- A Groq API key for analytics.
- Stripe API keys when testing checkout.

The current local configuration uses Celery's filesystem broker, so Redis is not required.

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd ecommerce-agent
```

### 2. Create and activate a virtual environment

```bash
python3.12 -m venv env
source env/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a PostgreSQL database named `ecommerce`. The current development defaults in `ecommerce/settings.py` are:

```text
Database: ecommerce
User:     postgres
Password: password
Host:     localhost
Port:     5432
```

Update those settings before using a different account or any production environment.

### 5. Create `.env`

Copy the safe sample file and replace placeholders.

```bash
cp .env.sample .env
```

At minimum, set the following values in `.env`:

```dotenv
GOOGLE_API_KEY=your_google_gemini_api_key
GROQ_SQL_API_KEY=your_groq_api_key
DATABASE_URL=postgresql://postgres:password@localhost:5432/ecommerce
STRIPE_PUBLISHABLE_KEY=pk_test_replace_me
STRIPE_SECRET_KEY=sk_test_replace_me
```

For local development without SMTP, keep `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

### 6. Run migrations and create a staff user

```bash
python manage.py migrate
python manage.py createsuperuser
```

## Running the project

Activate the virtual environment in each terminal. Start the following services from the project root.

### Django application

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/` for the storefront. Sign in with a staff/superuser account and open `http://127.0.0.1:8000/agent/` for the AI agent.

### Celery worker

```bash
celery -A ecommerce worker --loglevel=info
```

### Celery Beat scheduler

```bash
celery -A ecommerce beat --loglevel=info
```

Run both the worker and Beat when testing scheduled reports, price restoration, or emails.

## Useful commands

```bash
# Check Django configuration
python manage.py check

# Run the test suite
python manage.py test

# Show migration state
python manage.py showmigrations
```

## Project structure

```text
ecommerce/       Django settings, URLs, and Celery configuration
shop/            Store models, customer views, templates, and static assets
agent/           AI agent, tools, chat views, analytics, and Celery tasks
media/           Uploaded media in local development
celery_queue/    Filesystem-broker queue in local development
```

## License

This project is licensed under the [MIT License](LICENSE).
