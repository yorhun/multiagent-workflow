# Multi-Agent Workflow

This repository contains my project submission for the Agentic AI nanodegree program of Udacity. 

## Brief description

A multiagent workflow is implemented to process customer requests.

An orchestrator agent analyzes customer requests and coordinates specialized worker agents by calling them sequentially to check inventory stock status, calculate the quote (price) for the requested items, and order restock if necessary.

### Workflow run terminal output

![Terminal Output Clip](./docs/terminal_output_trimmed.gif)

## Project contents

### 1. Workflow Overview

**Workflow diagram:** 
![Workflow Diagram](./docs/beavers_choice_workflow.png)
Customer inquiries enter through the **Paper Factory Orchestrator** agent, which maps requests to catalog SKUs and coordinates the specialized worker agents by calling them sequentially as tools.

**Agent roster (max five as required):**
- **Paper Factory Orchestrator** (`paper_factory_orchestrator`) – a `pydantic-ai` agent that drives the full pipeline. It maps customer text to catalog SKUs, infers discount strategy and urgency, and calls the three worker agents in fixed sequence (inventory → quote → fulfillment) by invoking them as tools. It assembles the final structured output.
- **Stock Agent** (`stock_agent`) – handles inventory verification and replenishment. Tools: `tool_inventory_snapshot` (wraps `get_all_inventory`), `tool_item_stock_probe` (wraps `get_stock_level`), and `tool_plan_restock_purchase` (wraps `get_supplier_delivery_date` + `create_transaction`). It determines fulfillment capability per item and initiates supplier purchase orders when stock is insufficient, subject to a cash safety check (cost must not exceed 85% of available cash).
- **Quote Engineer** (`quote_engineer`) – develops pricing proposals. Tools: `tool_lookup_quote_history` (wraps `search_quote_history`), `tool_cash_window` (wraps `get_cash_balance`), and `tool_price_builder` (applies volume markup 28%/18%/12% and caps discounts at 15%). A deterministic `_ensure_quote_lines` post-processing step patches any missing or mis-priced lines using `tool_price_builder` and normalizes LLM-returned statuses against actual inventory data.
- **Fulfillment Agent** (`fulfillment_agent`) – generates the final customer-facing message. Tool: `tool_financial_snapshot` (wraps `generate_financial_report`). It does **not** record sales — sales are recorded deterministically inside `run_quote_agent` for all lines with status `ready`, `partial`, or `approved` before the fulfillment agent is called.

**Data flow summary:**
- The Orchestrator maps the customer request to up to four catalog SKUs and calls `run_inventory_agent`.
- Stock Agent checks stock levels per item and places future-dated supplier purchase orders for shortfalls within cash limits.
- Quote Agent builds priced lines using historical context, current cash, and `tool_price_builder`; a deterministic patch step corrects LLM output before returning. Sales for immediately available items are recorded at this stage via `tool_record_sale`.
- Fulfillment Agent receives the ready quote lines, calls `tool_financial_snapshot`, and composes a customer message that covers confirmed items, backorder ETAs, and delivery commitments — without exposing internal cash figures or margins.

### 2. Starter Helper Functions
- generate_sample_inventory(paper_supplies, coverage=0.4): produces a reproducible selection (seeded RNG) from the complete paper product list with random stock quantities (200–800) and minimum stock levels (50–150) to populate the initial SQLite database tables.
- init_database(db_engine): establishes the SQLite database structure (transactions, quote_requests, quotes, inventory) and populates it with initial records — including an opening cash balance of $50,000 recorded as a dummy sales transaction and initial stock orders for each generated inventory item.
- create_transaction(item_name, transaction_type, quantity, price, date, delivery_date=None): records either a `stock_orders` or `sales` entry in the transactions table and returns the generated row identifier. Accepts an optional `delivery_date` used by stock orders to indicate when goods become available.
- get_all_inventory(as_of_date): calculates available stock for each product by summing delivered stock orders and subtracting sales through a specified date, returning a `Dict[str, int]` of item names to stock levels (only items with positive stock are included).
- get_stock_level(item_name, as_of_date): performs the same calculation as get_all_inventory but focuses on a single product, returning a single-row DataFrame with columns `item_name` and `current_stock`.
- get_supplier_delivery_date(input_date_str, quantity): estimates delivery lead time using quantity-based thresholds (same day ≤10 units; +1 day ≤100; +4 days ≤1000; +7 days >1000) to support restocking planning.
- get_cash_balance(as_of_date): computes available funds by subtracting total stock purchase costs from total sales revenue recorded up to the given date.
- generate_financial_report(as_of_date): combines cash balance, inventory valuation, total assets, itemized inventory breakdown, and top-5 best-selling products by revenue into a dictionary suitable for management reporting.
- search_quote_history(search_terms, limit=5): queries the `quote_requests` and `quotes` tables using LIKE filters across customer responses and quote explanations to find comparable previous transactions that can inform pricing for new customer inquiries.

### 3. Testing the workflow

`project_starter.py` includes `run_test_scenarios()`, which processes all rows in `quote_requests_sample.csv` through the four-agent workflow and outputs final balances and customer responses to `test_results.csv`. Execution depends on the Udacity/Vocareum API key since all agents use `pydantic-ai` with OpenAI connectivity. (Configure `UDACITY_OPENAI_API_KEY` in `.env` then run `python project_starter.py`.)

### 4. Ideas for Improvement
- **Use a partially nonlinear workflow** - this would speed up the processing. For example the quote calculation or restock planning for separate items can be processed simultaneously.
- **Handle transactions and cash balance more systematically**
