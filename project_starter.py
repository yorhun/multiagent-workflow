import pandas as pd
import numpy as np
import os
import time
import json
import textwrap
import dotenv
import ast
from difflib import get_close_matches
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from sqlalchemy import create_engine, Engine
from pydantic import BaseModel, Field
from pydantic_ai import Agent, Tool, StructuredDict
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import UsageLimits

# ANSI color codes for terminal agent output
class C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    # Agent colors
    ORCH    = "\033[96m"   # Cyan       — Paper Factory Orchestrator
    INV     = "\033[93m"   # Yellow     — Stock Agent
    QUOTE   = "\033[95m"   # Magenta    — Quote Engineer
    FULFIL  = "\033[92m"   # Green      — Fulfillment Agent
    # Status colors
    WARN    = "\033[91m"   # Red        — warnings / errors
    UTIL    = "\033[37m"   # White/grey — utility functions
    HEADER  = "\033[1;96m" # Bold cyan  — section headers

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

VOC_BASE_URL = "https://openai.vocareum.com/v1"
CANONICAL_ITEM_NAMES = sorted({item["item_name"] for item in paper_supplies})
LOWER_CANONICAL_ITEM_NAMES = [name.lower() for name in CANONICAL_ITEM_NAMES]
PRICE_LOOKUP = {item["item_name"].lower(): item["unit_price"] for item in paper_supplies}
ITEM_NAME_SYNONYMS = {
    "heavy cardstock": "Cardstock",
    "card stock": "Cardstock",
    "colored cardstock": "Cardstock",
    "glossy a4 paper": "Glossy paper",
    "a4 glossy paper": "Glossy paper",
    "a4 paper": "A4 paper",
    "letter paper": "Letter-sized paper",
    "letter sized paper": "Letter-sized paper",
    "eco paper": "Eco-friendly paper",
    "recycled": "Recycled paper",
    "poster stock": "Poster paper",
    "banner": "Banner paper",
    # product synonyms
    "streamers": "Party streamers",
    "streamer": "Party streamers",
    "party streamer": "Party streamers",
    "washi tape": "Decorative adhesive tape (washi tape)",
    "decorative tape": "Decorative adhesive tape (washi tape)",
    "adhesive tape": "Decorative adhesive tape (washi tape)",
    "paper bags": "Paper party bags",
    "party bags": "Paper party bags",
    "name tags": "Name tags with lanyards",
    "lanyards": "Name tags with lanyards",
    "folders": "Presentation folders",
    "napkins": "Paper napkins",
    "cups": "Disposable cups",
    "plates": "Paper plates",
    # paper synonyms
    "colorful paper": "Colored paper",
    "colour paper": "Colored paper",
    "coloured paper": "Colored paper",
    "bright colored paper": "Bright-colored paper",
    "bright colour paper": "Bright-colored paper",
    "colorful poster paper": "Poster paper",
    "coloured poster paper": "Poster paper",
    "poster board": "Large poster paper (24x36 inches)",
    "poster boards": "Large poster paper (24x36 inches)",
    "kraft": "Kraft paper",
    "butcher": "Butcher paper",
    "crepe": "Crepe paper",
    "heavyweight paper": "Heavyweight paper",
    "heavy paper": "Heavyweight paper",
    "recycled paper": "Recycled paper",
}

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date (order date for stock_orders)
            "delivery_date": [],     # Expected arrival date (stock_orders only; NULL for sales)
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("files/quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("files/quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
            "delivery_date": None,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
                "delivery_date": initial_date,  # initial stock is available immediately
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"{C.WARN}[ERROR] Database init failed: {e}{C.RESET}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
    delivery_date: Optional[str] = None,
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
            "delivery_date": delivery_date,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"{C.WARN}[ERROR] Transaction failed: {e}{C.RESET}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders'
                     AND (delivery_date IS NULL OR delivery_date <= :as_of_date) THEN units
                WHEN transaction_type = 'sales'
                     AND transaction_date <= :as_of_date THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders'
                     AND (delivery_date IS NULL OR delivery_date <= :as_of_date) THEN units
                WHEN transaction_type = 'sales'
                     AND transaction_date <= :as_of_date THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"{C.UTIL}{C.DIM}[UTIL] get_supplier_delivery_date: qty={quantity} date='{input_date_str}'{C.RESET}")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"{C.WARN}[WARN] get_supplier_delivery_date: invalid date '{input_date_str}', using today{C.RESET}")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"{C.WARN}[ERROR] Cash balance query failed: {e}{C.RESET}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row) for row in result]

dotenv.load_dotenv()


def configure_openai_environment() -> str:
    """
    Ensure that pydantic-ai routes through the Vocareum proxy by setting OPENAI env vars.
    """
    key = (
        os.getenv("UDACITY_OPENAI_API_KEY")
        or os.getenv("VOC_OPENAI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not key:
        raise RuntimeError(
            "Missing UDACITY_OPENAI_API_KEY in your environment or .env file."
        )
    os.environ["OPENAI_API_KEY"] = key
    os.environ.setdefault("OPENAI_BASE_URL", VOC_BASE_URL)
    return key


def canonicalize_item_name(raw_name: str) -> str:
    """Map text to the closest match in the canonical item names."""
    if not raw_name:
        return ""
    key = raw_name.strip().lower()
    if key in ITEM_NAME_SYNONYMS:
        return ITEM_NAME_SYNONYMS[key]
    if key in PRICE_LOOKUP:
        idx = LOWER_CANONICAL_ITEM_NAMES.index(key)
        return CANONICAL_ITEM_NAMES[idx]
    for sku in CANONICAL_ITEM_NAMES:
        if sku.lower() in key:
            return sku
    matches = get_close_matches(key, LOWER_CANONICAL_ITEM_NAMES, n=1, cutoff=0.72)
    if matches:
        matched = matches[0]
        idx = LOWER_CANONICAL_ITEM_NAMES.index(matched)
        return CANONICAL_ITEM_NAMES[idx]
    return ""


class PlannedItem(BaseModel):
    requested_name: str
    normalized_item: str
    quantity: int = Field(ge=0)
    urgency: str
    notes: Optional[str] = None


class OrchestrationPlan(BaseModel):
    summary: str
    due_date: Optional[str] = None
    customer_priority: str
    discount_strategy: str
    needs_inventory: bool
    needs_reorder: bool
    needs_quote: bool
    needs_fulfillment: bool
    items: List[PlannedItem]


class InventoryLine(BaseModel):
    item_name: str
    requested_units: int
    available_units: int
    ready_units: int
    status: str
    action: str
    eta: Optional[str] = None
    notes: Optional[str] = None


class InventoryAssessment(BaseModel):
    lines: List[InventoryLine]
    decision_notes: str


class QuoteLine(BaseModel):
    item_name: str
    quantity: int
    unit_price: float
    line_total: float
    discount_pct: float
    status: str
    notes: str


class QuoteDecision(BaseModel):
    quote_lines: List[QuoteLine]
    declined_items: List[str]
    total_amount: float
    quote_explanation: str
    can_fulfill: bool


class FulfillmentSummary(BaseModel):
    fulfilled_items: List[str]
    recorded_transactions: List[int]
    delivery_notes: str
    customer_message: str


class FinalOrchestratorOutput(BaseModel):
    customer_message: str
    quote_total: float
    fulfilled_items: List[str]


ORCHESTRATOR_OUTPUT = StructuredDict(OrchestrationPlan.model_json_schema())
ORCHESTRATOR_FINAL_OUTPUT = StructuredDict(FinalOrchestratorOutput.model_json_schema())
INVENTORY_OUTPUT = StructuredDict(InventoryAssessment.model_json_schema())
QUOTE_OUTPUT = StructuredDict(QuoteDecision.model_json_schema())
FULFILLMENT_OUTPUT = StructuredDict(FulfillmentSummary.model_json_schema())


def tool_inventory_snapshot(as_of_date: str) -> Dict[str, Any]:
    """Retrieve complete inventory quantities across all products for a specified date."""
    return {"as_of_date": as_of_date, "inventory": get_all_inventory(as_of_date)}


def tool_item_stock_probe(item_name: str, as_of_date: str) -> Dict[str, Any]:
    """Check available stock quantity for one specific product at a given point in time."""
    canonical = canonicalize_item_name(item_name)
    if not canonical:
        return {"item_name": item_name, "error": "unrecognized SKU"}
    stock_df = get_stock_level(canonical, as_of_date)
    stock_value = int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0
    return {"item_name": canonical, "current_stock": stock_value, "as_of_date": as_of_date}


def tool_plan_restock_purchase(item_name: str, units: int, as_of_date: str) -> Dict[str, Any]:
    """Initiate a replenishment order from suppliers and log it with the estimated arrival date."""
    canonical = canonicalize_item_name(item_name)
    if not canonical or units <= 0:
        return {"status": "skipped", "reason": "invalid sku or units"}
    unit_price = PRICE_LOOKUP.get(canonical.lower())
    if unit_price is None:
        return {"status": "skipped", "reason": "missing price"}
    estimated_cost = round(unit_price * units, 2)
    available_cash = get_cash_balance(as_of_date)
    if estimated_cost > max(available_cash * 0.85, 1.0):
        return {
            "status": "deferred",
            "reason": f"cost ${estimated_cost:.2f} exceeds safe cash window ${available_cash:.2f}",
        }
    delivery_date = get_supplier_delivery_date(as_of_date, units)
    transaction_id = create_transaction(
        canonical,
        "stock_orders",
        units,
        estimated_cost,
        as_of_date,              # ORDER date — deducts from cash immediately
        delivery_date=delivery_date,  # arrival date — stock becomes available then
    )
    return {
        "status": "ordered",
        "item_name": canonical,
        "units": units,
        "cost": estimated_cost,
        "expected_delivery": delivery_date,
        "transaction_id": transaction_id,
    }


def tool_lookup_quote_history(keywords: List[str], limit: int = 5) -> List[Dict[str, Any]]:
    """Search past quotation records matching provided search terms."""
    keywords = [kw for kw in keywords if kw]
    return search_quote_history(keywords, limit=limit)


def tool_cash_window(as_of_date: str) -> Dict[str, Any]:
    """Provide current available funds to support purchasing and pricing decisions."""
    cash = get_cash_balance(as_of_date)
    return {"as_of_date": as_of_date, "cash_balance": round(cash, 2)}


def tool_price_builder(
    item_name: str,
    quantity: int,
    discount_pct: float = 0.0,
    expedite: bool = False,
) -> Dict[str, Any]:
    """Calculate final unit and total pricing with volume markups, discounts, and rush fees."""
    canonical = canonicalize_item_name(item_name)
    if not canonical or quantity <= 0:
        return {"error": "invalid input"}
    unit_price = PRICE_LOOKUP.get(canonical.lower())
    if unit_price is None:
        return {"error": "price lookup failed"}
    volume_markup = 0.28 if quantity < 500 else 0.18
    if quantity >= 2000:
        volume_markup = 0.12
    base_price = unit_price * (1 + volume_markup)
    capped_discount = max(min(discount_pct, 15.0), 0.0)
    discounted_price = base_price * (1 - capped_discount / 100)
    if expedite:
        discounted_price *= 1.02
    final_unit = round(max(discounted_price, unit_price * 0.8), 4)
    line_total = round(final_unit * quantity, 2)
    return {
        "item_name": canonical,
        "unit_price": final_unit,
        "line_total": line_total,
        "discount_pct": capped_discount,
        "applied_markup": volume_markup,
        "expedite": expedite,
    }


def tool_record_sale(
    item_name: str,
    units: int,
    unit_price: float,
    as_of_date: str,
    note: str = "",
) -> Dict[str, Any]:
    """Register a completed sale in the transaction ledger and return its unique identifier."""
    canonical = canonicalize_item_name(item_name)
    if not canonical or units <= 0:
        return {"status": "skipped", "reason": "invalid sale payload"}
    total_price = round(unit_price * units, 2)
    transaction_id = create_transaction(
        canonical,
        "sales",
        units,
        total_price,
        as_of_date,
    )
    return {
        "status": "recorded",
        "item_name": canonical,
        "units": units,
        "unit_price": unit_price,
        "total_price": total_price,
        "note": note,
        "transaction_id": transaction_id,
    }


def tool_financial_snapshot(as_of_date: str) -> Dict[str, Any]:
    """Generate a concise financial summary suitable for sharing with clients."""
    return generate_financial_report(as_of_date)


class BeaverChoiceSystem:
    """Encapsulates the Beaver's Choice multi-agent workflow."""

    def __init__(self, model_name: str = "gpt-4o-mini") -> None:
        configure_openai_environment()
        model_ref = f"openai:{model_name}"
        orchestration_settings = ModelSettings(temperature=0.2, max_output_tokens=15000)
        worker_settings = ModelSettings(temperature=0.15, max_output_tokens=10000)

        self.inventory_agent = Agent(
            model_ref,
            name="stock_agent",
            instructions=self._build_inventory_instructions(),
            tools=[
                Tool(tool_inventory_snapshot),
                Tool(tool_item_stock_probe),
                Tool(tool_plan_restock_purchase),
            ],
            output_type=INVENTORY_OUTPUT,
            model_settings=worker_settings,
        )
        self.quote_agent = Agent(
            model_ref,
            name="quote_engineer",
            instructions=self._build_quote_instructions(),
            tools=[
                Tool(tool_lookup_quote_history),
                Tool(tool_cash_window),
                Tool(tool_price_builder),
            ],
            output_type=QUOTE_OUTPUT,
            model_settings=worker_settings,
        )
        self.fulfillment_agent = Agent(
            model_ref,
            name="fulfillment_agent",
            instructions=self._build_fulfillment_instructions(),
            tools=[
                Tool(tool_financial_snapshot),
            ],
            output_type=FULFILLMENT_OUTPUT,
            model_settings=worker_settings,
        )
        self.orchestrator = Agent(
            model_ref,
            name="paper_factory_orchestrator",
            instructions=self._build_orchestrator_instructions(),
            tools=self._build_agent_tools(),
            output_type=ORCHESTRATOR_FINAL_OUTPUT,
            model_settings=orchestration_settings,
        )

    def process_request(self, request_row: Dict[str, Any]) -> Dict[str, Any]:
        payload = self._prepare_payload(request_row)
        self._pipeline_result: Optional[Dict[str, Any]] = None
        self._non_catalog_items: List[str] = []
        self._recorded_sales: List[str] = []
        self._last_quote_result: Optional[Dict[str, Any]] = None
        try:
            result = self.orchestrator.run_sync(self._orchestrator_prompt(payload)).output
            customer_message = result.get("customer_message", "")
            quote_total = result.get("quote_total", 0.0)
            fulfilled_items = result.get("fulfilled_items", [])
            fulfillment_status = self._pipeline_result.get("fulfillment_status", "") if self._pipeline_result else ""
            # Fall back to the value captured directly from run_fulfillment_agent
            # if the orchestrator LLM left customer_message empty in its structured output.
            if not customer_message and self._pipeline_result:
                customer_message = self._pipeline_result.get("customer_message", "")
                if not quote_total:
                    quote_total = self._pipeline_result.get("quote_total", 0.0)
                if not fulfilled_items:
                    fulfilled_items = self._pipeline_result.get("fulfilled_items", [])
            # Derive availability fields from pipeline result or recorded sales fallback
            if self._pipeline_result:
                items_immediately_available = self._pipeline_result.get("items_immediately_available", [])
                items_pending_on_restock = self._pipeline_result.get("items_pending_on_restock", [])
            else:
                _non_catalog_set_fb = {name.lower() for name in self._non_catalog_items}
                items_immediately_available = {
                    name: next(
                        (line.get("quantity", 0) for line in (self._last_quote_result or {}).get("quote_lines", [])
                         if line.get("item_name", "").lower() == name.lower()),
                        0,
                    )
                    for name in self._recorded_sales
                    if name.lower() not in _non_catalog_set_fb
                }
                _fb_pending = {}
                for _fb_line in (self._last_quote_result or {}).get("quote_lines", []):
                    if _fb_line.get("status", "").lower() == "backordered" and _fb_line.get("item_name", "").lower() not in _non_catalog_set_fb:
                        _fb_name = _fb_line.get("item_name", "")
                        _fb_qty = _fb_line.get("quantity", 0)
                        _fb_eta = None
                        _fb_notes = _fb_line.get("notes", "")
                        if "restock expected by " in _fb_notes:
                            _fb_eta = _fb_notes.split("restock expected by ")[-1].split(".")[0]
                        _fb_pending[_fb_name] = {"quantity": _fb_qty, "eta": _fb_eta or "TBD"}
                items_pending_on_restock = _fb_pending
            return {
                "customer_message": customer_message,
                "quote_total": quote_total,
                "fulfilled_items": fulfilled_items,
                "fulfillment_status": fulfillment_status,
                "items_immediately_available": items_immediately_available,
                "items_pending_on_restock": items_pending_on_restock,
                "items_not_available": self._non_catalog_items,
            }
        except Exception as exc:
            message = (
                "We encountered an internal routing issue while drafting your plan. "
                "Please retry shortly or contact your account rep."
            )
            print(f"{C.WARN}[WARN] Paper Factory Orchestrator failure: {exc}{C.RESET}")
            return {
                "customer_message": message,
                "error": str(exc),
                "quote_total": 0.0,
                "fulfilled_items": [],
                "fulfillment_status": "No, see detailed response",
                "items_immediately_available": [],
                "items_pending_on_restock": [],
                "items_not_available": self._non_catalog_items,
            }

    def _build_agent_tools(self) -> list:
        """Create Tool wrappers around the worker agents for the orchestrator."""

        def run_inventory_agent(
            items_json: str,
            request_date: str,
            due_date: str,
            need_size: str,
        ) -> str:
            """Check inventory levels and plan restocks. items_json is a JSON array of objects with keys: normalized_item, quantity, urgency."""
            print(f"{C.INV}[Stock Agent] Starting...{C.RESET}")
            try:
                items = json.loads(items_json)
            except Exception:
                return json.dumps({"error": "invalid items_json", "lines": [], "decision_notes": ""})
            # Deduplicate items by normalized_item — the LLM may split a single compound
            # descriptor (e.g. "A4 glossy paper") into multiple entries. Keep only the first
            # occurrence of each canonical name so each physical SKU is counted once.
            seen_normalized: Dict[str, bool] = {}
            deduped_items = []
            for item in items:
                key = canonicalize_item_name(item.get("normalized_item", "")).lower()
                if not key:
                    key = item.get("normalized_item", "").lower()
                if key and key in seen_normalized:
                    print(f"{C.INV}{C.DIM}[Stock Agent] Dedup: dropping '{item.get('normalized_item')}' (→'{key}'){C.RESET}")
                    continue
                if key:
                    seen_normalized[key] = True
                deduped_items.append(item)
            items = deduped_items
            payload = {
                "items": items,
                "request_date": request_date,
                "due_date": due_date or request_date,
                "need_size": need_size,
            }
            try:
                result = self.inventory_agent.run_sync(self._inventory_prompt(payload)).output
                print(f"{C.INV}[Stock Agent] Done.{C.RESET}")
                return json.dumps(result)
            except Exception as exc:
                print(f"{C.WARN}[Stock Agent] WARN: {exc}{C.RESET}")
                return json.dumps({"error": str(exc), "lines": [], "decision_notes": ""})

        def run_quote_agent(
            items_json: str,
            inventory_result_json: str,
            request_date: str,
            customer_job: str,
            customer_event: str,
            discount_strategy: str,
        ) -> str:
            """Build pricing quotes based on items and inventory availability. Pass the full inventory_result_json from run_inventory_agent."""
            try:
                items = json.loads(items_json)
            except Exception:
                items = []
            try:
                inventory_result = json.loads(inventory_result_json) if inventory_result_json else None
            except Exception:
                inventory_result = None
            print(f"{C.QUOTE}[Quote Engineer] Starting...{C.RESET}")
            customer_context = {"job": customer_job, "event": customer_event}
            payload = {
                "items": items,
                "inventory": inventory_result["lines"] if inventory_result and inventory_result.get("lines") else [],
                "request_date": request_date,
                "customer_context": customer_context,
                "discount_strategy": discount_strategy,
            }
            try:
                result = self.quote_agent.run_sync(self._quote_prompt(payload), usage_limits=UsageLimits(request_limit=20)).output
                print(f"{C.QUOTE}[Quote Engineer] Done.{C.RESET}")
            except Exception as exc:
                print(f"{C.WARN}[Quote Engineer] WARN: {exc}{C.RESET}")
                result = None
            actionable_items = [
                item for item in items
                if item.get("normalized_item") and item.get("catalog_match", True) and item.get("quantity", 0) > 0
            ]
            plan = {"discount_strategy": discount_strategy}
            result = self._ensure_quote_lines(result, inventory_result, actionable_items, plan)
            if result is None:
                result = {"quote_lines": [], "declined_items": [], "total_amount": 0.0, "quote_explanation": "", "can_fulfill": False}

            # Track non-catalog items: only items that cannot be resolved to any catalog SKU.
            # The LLM's catalog_match flag is unreliable (it sometimes marks valid items as False),
            # so canonicalize_item_name is the sole authority here.
            self._non_catalog_items = [
                item.get("normalized_item", "Unknown")
                for item in items
                if not canonicalize_item_name(item.get("normalized_item", ""))
            ]

            # Record sales immediately for all in-stock items
            # Include "approved" — _ensure_quote_lines preserves LLM status "approved" for ready items
            AVAILABLE_STATUSES = {"ready", "partial", "approved"}
            self._recorded_sales = []
            for line in result.get("quote_lines", []):
                if line.get("status", "").lower() in AVAILABLE_STATUSES:
                    item_name = line.get("item_name", "")
                    qty = line.get("quantity", 0)
                    up = line.get("unit_price", 0.0)
                    if item_name and qty > 0 and up > 0:
                        sale_result = tool_record_sale(item_name, qty, up, request_date)
                        if sale_result.get("status") == "recorded":
                            self._recorded_sales.append(item_name)
                            print(f"{C.FULFIL}[Fulfillment Agent] Recorded sale: {qty}x {item_name} @ ${up:.4f}{C.RESET}")

            for line in result.get("quote_lines", []):
                if line.get("status", "").lower() == "backordered":
                    item_name = line.get("item_name", "")
                    qty = line.get("quantity", 0)
                    up = line.get("unit_price", 0.0)
                    if item_name and qty > 0:
                        eta = None
                        if inventory_result and inventory_result.get("lines"):
                            for inv_line in inventory_result["lines"]:
                                if inv_line.get("item_name", "").lower() == item_name.lower():
                                    eta = inv_line.get("eta")
                                    break
                        if eta is None:
                            notes = line.get("notes", "")
                            if "restock expected by " in notes:
                                eta = notes.split("restock expected by ")[-1].split(".")[0]
                        eta_str = eta if eta else "TBD"
                        print(f"{C.FULFIL}  Expected sale pending on restock: {qty}x {item_name} @ ${up:.4f} - to be fulfilled {eta_str}{C.RESET}")

            self._last_quote_result = result
            return json.dumps(result)

        def run_fulfillment_agent(
            quote_result_json: str,
            inventory_result_json: str,
            request_date: str,
            due_date: str,
            customer_job: str,
            customer_event: str,
        ) -> str:
            """Record confirmed sales and generate the final customer message. Call only when quote has ready or partial lines."""
            try:
                quote_result = json.loads(quote_result_json)
            except Exception:
                quote_result = None
            try:
                inventory_result = json.loads(inventory_result_json) if inventory_result_json else None
            except Exception:
                inventory_result = None
            fulfillment_result = None
            ready_lines = []
            AVAILABLE_STATUSES = {"ready", "partial", "approved"}
            if quote_result:
                ready_lines = [
                    line for line in quote_result.get("quote_lines", [])
                    if line.get("status", "").lower() in AVAILABLE_STATUSES
                ]
            # Sales were already recorded in run_quote_agent; reuse that list
            pre_recorded_items: List[str] = list(self._recorded_sales)
            print(f"{C.FULFIL}[Fulfillment Agent] Starting...{C.RESET}")
            if ready_lines:
                fulfillment_payload = {
                    "lines": ready_lines,
                    "request_date": request_date,
                    "due_date": due_date or request_date,
                    "quote_total": quote_result.get("total_amount", 0.0) if quote_result else 0.0,
                    "inventory": inventory_result["lines"] if inventory_result and inventory_result.get("lines") else [],
                }
                try:
                    fulfillment_result = self.fulfillment_agent.run_sync(
                        self._fulfillment_prompt(fulfillment_payload)
                    ).output
                except Exception as exc:
                    print(f"{C.WARN}[Fulfillment Agent] WARN: {exc}{C.RESET}")
            # Ensure fulfilled_items reflects what was actually recorded
            if fulfillment_result is None and pre_recorded_items:
                fulfillment_result = {
                    "fulfilled_items": pre_recorded_items,
                    "recorded_transactions": [],
                    "delivery_notes": "",
                    "customer_message": "",
                }
            elif fulfillment_result is not None and not fulfillment_result.get("fulfilled_items"):
                fulfillment_result["fulfilled_items"] = pre_recorded_items
            print(f"{C.FULFIL}[Fulfillment Agent] Done. Building customer message...{C.RESET}")
            payload = {"job": customer_job, "event": customer_event, "request": "", "request_date": request_date, "need_size": ""}
            plan = {"due_date": due_date}
            customer_message = self._final_customer_message(payload, plan, inventory_result, quote_result, fulfillment_result)
            quote_total = quote_result.get("total_amount", 0.0) if quote_result else 0.0
            fulfilled_items = fulfillment_result["fulfilled_items"] if fulfillment_result else []
            has_backorder = any(
                line.get("status", "").lower() == "backordered"
                for line in (quote_result or {}).get("quote_lines", [])
            )
            if fulfilled_items and not has_backorder:
                fulfillment_status = "Yes, entire has been successfully fulfilled at the time of request"
            else:
                fulfillment_status = "No, see detailed response"
            non_catalog_set = {name.lower() for name in self._non_catalog_items}
            items_immediately_available = {
                line.get("item_name", ""): line.get("quantity", 0)
                for line in (quote_result or {}).get("quote_lines", [])
                if line.get("status", "").lower() in AVAILABLE_STATUSES
                and line.get("item_name", "").lower() not in non_catalog_set
            }
            inv_lines_lookup = {
                inv_l.get("item_name", "").lower(): inv_l
                for inv_l in (inventory_result or {}).get("lines", [])
            }
            items_pending_on_restock = {}
            for _bo_line in (quote_result or {}).get("quote_lines", []):
                if _bo_line.get("status", "").lower() == "backordered" and _bo_line.get("item_name", "").lower() not in non_catalog_set:
                    _bo_name = _bo_line.get("item_name", "")
                    _bo_qty = _bo_line.get("quantity", 0)
                    _bo_inv = inv_lines_lookup.get(_bo_name.lower(), {})
                    _bo_eta = _bo_inv.get("eta")
                    if _bo_eta is None:
                        _bo_notes = _bo_line.get("notes", "")
                        if "restock expected by " in _bo_notes:
                            _bo_eta = _bo_notes.split("restock expected by ")[-1].split(".")[0]
                    items_pending_on_restock[_bo_name] = {"quantity": _bo_qty, "eta": _bo_eta or "TBD"}
            self._pipeline_result = {
                "customer_message": customer_message,
                "quote_total": quote_total,
                "fulfilled_items": fulfilled_items,
                "fulfillment_status": fulfillment_status,
                "items_immediately_available": items_immediately_available,
                "items_pending_on_restock": items_pending_on_restock,
            }
            return json.dumps(self._pipeline_result)

        return [Tool(run_inventory_agent), Tool(run_quote_agent), Tool(run_fulfillment_agent)]

    def _ensure_quote_lines(
        self,
        quote_result: Optional[Dict[str, Any]],
        inventory_result: Optional[Dict[str, Any]],
        actionable_items: List[Dict[str, Any]],
        plan: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Guarantee that every item with available inventory gets a priced quote
        line.  The LLM-based quote agent frequently returns 0.0 or marks
        available items as 'insufficient', so we patch the result
        deterministically using tool_price_builder.
        """
        approved_statuses = {"ready", "approved", "partial"}

        # Build a lookup: canonical_item_name(lower) -> inventory line
        # Canonicalize the inventory agent's item names so they match the orchestrator's
        # normalized_item values even when the LLM used slightly different wording.
        inv_lookup: Dict[str, Dict] = {}
        if inventory_result and inventory_result.get("lines"):
            for inv in inventory_result["lines"]:
                raw_name = inv.get("item_name", "")
                canonical = canonicalize_item_name(raw_name)
                key = (canonical or raw_name).lower()
                inv_lookup[key] = inv
                # Also index by the raw name as a fallback
                if raw_name.lower() != key:
                    inv_lookup[raw_name.lower()] = inv

        # Determine which items have available stock (fully or partially)
        quotable: List[Dict[str, Any]] = []
        for item in actionable_items:
            name = item.get("normalized_item", "")
            qty = item.get("quantity", 0)
            if not name or qty <= 0:
                continue
            inv = inv_lookup.get(name.lower())
            if inv:
                status = inv.get("status", "").lower()
                avail = inv.get("available_units", 0) or inv.get("ready_units", 0)
                if status in {"ready", "available"} or avail > 0:
                    quotable_qty = min(qty, avail) if avail > 0 else qty
                    if quotable_qty > 0:
                        quotable.append({"item_name": name, "quantity": quotable_qty})
            else:
                # No inventory info — still attempt to quote (item may exist)
                quotable.append({"item_name": name, "quantity": qty})

        # Initialise quote_result if the agent didn't produce one
        if quote_result is None:
            quote_result = {
                "quote_lines": [],
                "declined_items": [],
                "total_amount": 0.0,
                "quote_explanation": "",
                "can_fulfill": False,
            }

        # Normalise statuses on existing LLM quote lines using actual inventory data.
        # The LLM often returns "insufficient"/"unavailable" for out-of-stock items that
        # should be "backordered", or "insufficient" for in-stock items that should be
        # "ready"/"partial".  Fix these before any downstream filtering.
        bad_statuses = {"insufficient", "declined", "unavailable"}
        for line in quote_result.get("quote_lines", []):
            if line.get("status", "").lower() not in bad_statuses:
                continue
            item_key = line.get("item_name", "").lower()
            inv = inv_lookup.get(item_key, {})
            avail = inv.get("available_units", 0) or inv.get("ready_units", 0)
            qty = line.get("quantity", 0)
            if avail >= qty:
                line["status"] = "ready"
            elif avail > 0:
                line["status"] = "partial"
            else:
                line["status"] = "backordered"

        # Cap partial line quantities to actual available stock.
        # The LLM frequently marks a line "partial" but leaves quantity = full requested amount.
        # This would cause the recorded sale and items_immediately_available to show the full
        # requested qty instead of only the units genuinely in stock.
        for line in quote_result.get("quote_lines", []):
            if line.get("status", "").lower() != "partial":
                continue
            item_key = line.get("item_name", "").lower()
            inv = inv_lookup.get(item_key, {})
            avail = inv.get("available_units", 0) or inv.get("ready_units", 0)
            if avail > 0 and line.get("quantity", 0) > avail:
                line["quantity"] = avail
                up = line.get("unit_price", 0)
                if up > 0:
                    line["line_total"] = round(avail * up, 2)

        # Which items already have an approved quote line?
        existing_approved = {
            line.get("item_name", "").lower()
            for line in quote_result.get("quote_lines", [])
            if line.get("status", "").lower() in approved_statuses
        }

        # Fill in missing lines using the deterministic price_builder
        discount = 0.0
        strategy = plan.get("discount_strategy", "balanced").lower()
        if "non-profit" in strategy or "nonprofit" in strategy:
            discount = 10.0
        elif "aggressive" in strategy:
            discount = 5.0

        for q in quotable:
            if q["item_name"].lower() in existing_approved:
                continue
            pricing = tool_price_builder(
                item_name=q["item_name"],
                quantity=q["quantity"],
                discount_pct=discount,
            )
            if "error" in pricing:
                continue
            inv = inv_lookup.get(q["item_name"].lower(), {})
            avail = inv.get("available_units", 0) or inv.get("ready_units", 0)
            status = "ready" if avail >= q["quantity"] else "partial"
            quote_result["quote_lines"].append({
                "item_name": pricing["item_name"],
                "quantity": q["quantity"],
                "unit_price": pricing["unit_price"],
                "line_total": pricing["line_total"],
                "discount_pct": pricing["discount_pct"],
                "status": status,
                "notes": f"{q['quantity']} units at ${pricing['unit_price']:.4f} each",
            })

        # Add backordered lines for out-of-stock items and the unfulfilled shortfall of
        # partial items.  These are included in the quote total so the customer sees the
        # full order value.
        # Exclude lines where LLM left unit_price=0 so they can be re-priced deterministically.
        existing_in_quote = {
            line.get("item_name", "").lower()
            for line in quote_result.get("quote_lines", [])
            if line.get("unit_price", 0) > 0
        }
        existing_backorder = {
            line.get("item_name", "").lower()
            for line in quote_result.get("quote_lines", [])
            if line.get("status", "").lower() == "backordered"
        }
        for item in actionable_items:
            name = item.get("normalized_item", "")
            qty = item.get("quantity", 0)
            if not name or qty <= 0:
                continue
            inv = inv_lookup.get(name.lower())
            if inv:
                avail = inv.get("available_units", 0) or inv.get("ready_units", 0)
                eta = inv.get("eta")
                eta_note = f"restock expected by {eta}" if eta else "restock has been ordered"

                if avail == 0 and name.lower() not in existing_in_quote:
                    # Fully out of stock — backorder the full quantity
                    backorder_qty = qty
                    pricing = tool_price_builder(item_name=name, quantity=backorder_qty, discount_pct=discount)
                    if "error" not in pricing:
                        quote_result["quote_lines"].append({
                            "item_name": pricing["item_name"],
                            "quantity": backorder_qty,
                            "unit_price": pricing["unit_price"],
                            "line_total": pricing["line_total"],
                            "discount_pct": pricing["discount_pct"],
                            "status": "backordered",
                            "notes": (
                                f"Out of stock; {eta_note}. "
                                f"{backorder_qty} units at ${pricing['unit_price']:.4f} each."
                            ),
                        })
                        existing_in_quote.add(name.lower())

                elif 0 < avail < qty and name.lower() not in existing_backorder:
                    # Partial stock — a ready/partial line already covers `avail` units;
                    # add a separate backordered line for the shortfall.
                    shortfall = qty - avail
                    pricing = tool_price_builder(item_name=name, quantity=shortfall, discount_pct=discount)
                    if "error" not in pricing:
                        quote_result["quote_lines"].append({
                            "item_name": pricing["item_name"],
                            "quantity": shortfall,
                            "unit_price": pricing["unit_price"],
                            "line_total": pricing["line_total"],
                            "discount_pct": pricing["discount_pct"],
                            "status": "backordered",
                            "notes": (
                                f"Partial stock; {shortfall} units on backorder. {eta_note}. "
                                f"{shortfall} units at ${pricing['unit_price']:.4f} each."
                            ),
                        })
                        existing_backorder.add(name.lower())

        # Recalculate line_totals & overall total from approved + backordered lines
        for line in quote_result.get("quote_lines", []):
            qty = line.get("quantity", 0)
            up = line.get("unit_price", 0)
            if qty > 0 and up > 0:
                line["line_total"] = round(up * qty, 2)
            elif qty > 0 and up == 0:
                # LLM returned a line without pricing — patch with price_builder
                pricing = tool_price_builder(
                    item_name=line.get("item_name", ""),
                    quantity=qty,
                    discount_pct=discount,
                )
                if "error" not in pricing:
                    line["unit_price"] = pricing["unit_price"]
                    line["line_total"] = pricing["line_total"]

        total = sum(
            line.get("line_total", 0.0)
            for line in quote_result.get("quote_lines", [])
            if line.get("status", "").lower() in (approved_statuses | {"backordered"})
        )
        quote_result["total_amount"] = round(total, 2)

        if total > 0:
            quote_result["can_fulfill"] = True

        return quote_result

    def _prepare_payload(self, row: Dict[str, Any]) -> Dict[str, Any]:
        request_date = row["request_date"]
        if isinstance(request_date, datetime):
            request_iso = request_date.strftime("%Y-%m-%d")
        else:
            request_iso = str(request_date)
        return {
            "job": row.get("job", "customer"),
            "need_size": row.get("need_size", ""),
            "event": row.get("event", ""),
            "request": row.get("request", ""),
            "request_date": request_iso,
        }

    def _build_orchestrator_instructions(self) -> str:
        allowed = ", ".join(CANONICAL_ITEM_NAMES)
        return textwrap.dedent(
            f"""
            You are the orchestrator for a paper factory called Beaver's Choice. You coordinate the full order pipeline by calling your tools in sequence.

            CRITICAL: Call exactly ONE tool at a time. Never call multiple tools in parallel or simultaneously. Wait for each tool to return before calling the next.

            STEP 1 — Identify SKUs: Map customer text to <=4 items from this FULL catalog: {allowed}.
            Use the closest matching SKU name exactly as written. For items with absolutely no catalog match
            (e.g. balloons, food, electronics), keep the original requested name as normalized_item and set catalog_match to false.
            Common items like streamers, cups, napkins, envelopes, poster paper all have matches.

            CRITICAL — one item description = ONE SKU entry. Never split a single item into multiple SKUs.
            When a request uses compound descriptors (e.g. "A4 glossy paper", "colored cardstock"),
            always pick the MOST SPECIFIC SKU that matches. For example:
              - "A4 glossy paper" → "Glossy paper" only (NOT both "A4 paper" AND "Glossy paper")
              - "colored cardstock" → "Cardstock" only (NOT both "Colored paper" AND "Cardstock")
            Each distinct physical item the customer requests must appear exactly once in items_json.

            STEP 2 — Determine context: infer discount_strategy (balanced/aggressive/non-profit), due_date (use request_date if not specified), and urgency (high/medium/low) per item.

            STEP 3 — Call run_inventory_agent ONCE with:
            - items_json: JSON array of objects with keys normalized_item (exact SKU name or original name if no match), quantity (int), urgency, catalog_match (true/false, default true)
            - request_date, due_date, need_size
            Wait for it to finish before proceeding.

            STEP 4 — Call run_quote_agent ONCE with:
            - items_json: same array as step 3
            - inventory_result_json: the full string returned by run_inventory_agent
            - request_date, customer_job, customer_event, discount_strategy
            Wait for it to finish before proceeding.

            STEP 5 — If quote_result total_amount > 0 or any quote line has status ready/partial, call run_fulfillment_agent ONCE with:
            - quote_result_json: the full string returned by run_quote_agent
            - inventory_result_json: the full string returned by run_inventory_agent
            - request_date, due_date, customer_job, customer_event

            STEP 6 — Return the final output using the customer_message, quote_total, and fulfilled_items from run_fulfillment_agent.
            If fulfillment was skipped, set customer_message from the quote result, quote_total from the quote, fulfilled_items to [].

            Always run all steps even for small orders. Never skip inventory or quote. Never repeat a tool call.
            """
        ).strip()

    def _build_inventory_instructions(self) -> str:
        return textwrap.dedent(
            """
            You are Stock Agent. Steps:
            1. Call inventory_snapshot first to see overall stock for the given request date.
            2. For each requested item call item_stock_probe before deciding status.
            3. If stock is insufficient but reordering is allowed, call plan_restock_purchase with the missing units.
            4. Produce JSON with a line per item describing the decision. ready_units represents what can ship by the due date.
            """
        ).strip()

    def _build_quote_instructions(self) -> str:
        return textwrap.dedent(
            """
            You are Quote Engineer. Follow these steps exactly ONCE each — do not repeat any tool call:
            1. Call quote_lookup ONCE with relevant keywords.
            2. Call cash_window ONCE.
            3. Call price_builder ONCE per approved item (one call per item, never repeat for the same item).
            4. Return your structured output.
            Decline lines that inventory marked as unavailable and justify them in quote_explanation.
            
            CRITICAL: Calculate total_amount as the SUM of all line_total values from quote_lines 
            where status is "ready", "approved", or "partial". If no lines are approved, total_amount should be 0.0.
            Do NOT leave total_amount as 0.0 if there are approved quote lines.
            
            IMPORTANT: For every approved quote line, include clear notes explaining:
            - The quantity requested and unit price
            - Any discounts applied and why (e.g., "non-profit discount", "bulk order discount")
            - Current availability status from inventory
            
            Your quote_explanation should be customer-friendly and transparent, explaining:
            - The total quote amount and how it was calculated
            - Which items are included and their pricing
            - Which items (if any) cannot be fulfilled and why
            - Any special pricing considerations (discounts, volume pricing, etc.)
            
            Do not expose internal profit margins or sensitive company information.
            """
        ).strip()

    def _build_fulfillment_instructions(self) -> str:
        return textwrap.dedent(
            """
            You are Fulfillment Agent. Sales have already been recorded. Your tasks are:
            - Summarize logistics referencing delivery windows from the inventory notes.
            - Pull a financial_snapshot to mention overall readiness (do not expose cash balances exactly;
              speak qualitatively in customer_message).

            IMPORTANT: Your customer_message should be comprehensive and transparent:
            - Confirm what items are included in the order
            - Provide clear delivery timing for items in stock vs items on backorder
            - Explain the fulfillment plan in customer-friendly language
            - Always reference the provided Quote total as the total order value — do not recalculate it
            - Do NOT reveal exact profit margins, internal cash balances, or system error messages
            - Do NOT include any personally identifiable information beyond what's needed
            
            Example: "Your order for 100 units of A4 paper at $0.05 each ($5.00 total) has been confirmed.
            50 units are available for immediate shipment, and the remaining 50 units will arrive from our
            supplier on March 15th, after which we can complete delivery."
            """
        ).strip()

    def _orchestrator_prompt(self, payload: Dict[str, Any]) -> str:
        return textwrap.dedent(
            f"""
            Customer role: {payload['job']}
            Event: {payload['event']} (size: {payload['need_size']})
            Request date: {payload['request_date']}
            Full text:
            {payload['request']}
            """
        ).strip()

    def _inventory_prompt(self, payload: Dict[str, Any]) -> str:
        return textwrap.dedent(
            f"""
            Request date: {payload['request_date']}
            Due by: {payload['due_date']}
            Need size: {payload['need_size']}
            Items:
            {json.dumps(payload['items'], indent=2)}
            """
        ).strip()

    def _quote_prompt(self, payload: Dict[str, Any]) -> str:
        return textwrap.dedent(
            f"""
            Request date: {payload['request_date']}
            Customer metadata: job {payload['customer_context']['job']}, event {payload['customer_context']['event']}
            Discount strategy: {payload['discount_strategy']}
            Inventory context:
            {json.dumps(payload['inventory'], indent=2)}
            Requested items:
            {json.dumps(payload['items'], indent=2)}
            Use quote_lookup keywords extracted from the request narrative and event type.
            """
        ).strip()

    def _fulfillment_prompt(self, payload: Dict[str, Any]) -> str:
        return textwrap.dedent(
            f"""
            Request date: {payload['request_date']}
            Promised delivery date: {payload['due_date']}
            Quote total: {payload['quote_total']}
            Ready lines:
            {json.dumps(payload['lines'], indent=2)}
            Inventory notes:
            {json.dumps(payload['inventory'], indent=2)}
            """
        ).strip()

    def _format_item_status_note(
        self,
        item_name: str,
        requested: int,
        avail: int,
        eta: Optional[str],
        all_quote_lines: Optional[List[Dict]] = None,
    ) -> str:
        """
        Format a status note for an out-of-stock or partially available item,
        including price info. Follows the template:
          quote amount → available stock status → restock ETA → delivery commitment.
        """
        # Try to get unit_price (and missing quantity) from any matching quote line first
        unit_price: Optional[float] = None
        if all_quote_lines:
            for ql in all_quote_lines:
                if ql.get("item_name", "").lower() == item_name.lower():
                    if ql.get("unit_price", 0) > 0:
                        unit_price = ql["unit_price"]
                    if not requested:
                        requested = ql.get("quantity", 0)
                    break
        # Fall back to price_builder for a deterministic estimate
        if unit_price is None and requested > 0:
            pricing = tool_price_builder(item_name=item_name, quantity=requested)
            if "error" not in pricing:
                unit_price = pricing.get("unit_price")

        line_total = round(unit_price * requested, 2) if unit_price else None
        shortage = max(0, requested - avail)

        if avail > 0 and shortage > 0:
            # Partial: some units available now, rest on restock
            parts = []
            if unit_price and line_total:
                parts.append(
                    f"We can provide a quote of ${line_total:.2f} for {requested} units of {item_name} "
                    f"at ${unit_price:.2f} each."
                )
            if eta:
                parts.append(
                    f"Currently {avail} units are available in stock, and the remaining {shortage} units "
                    f"will arrive via supplier restock on {eta}."
                )
                parts.append("Once the restock arrives, we can complete the order and confirm delivery.")
            else:
                parts.append(f"Currently {avail} units are available in stock.")
            return " ".join(parts)
        else:
            # Fully out of stock
            if unit_price and line_total:
                if eta:
                    return (
                        f"{item_name} is currently out of stock with a restock order expected by {eta}. "
                        f"When available, we can provide {requested} units at ${unit_price:.2f} each "
                        f"(total ${line_total:.2f})."
                    )
                return (
                    f"{item_name} is currently out of stock. When available, we can provide "
                    f"{requested} units at ${unit_price:.2f} each (total ${line_total:.2f})."
                )
            if eta:
                return (
                    f"{item_name} is currently out of stock; a restock order has been placed with "
                    f"expected delivery on {eta}."
                )
            return f"{item_name} could not be included at this time."

    def _final_customer_message(
        self,
        payload: Dict[str, Any],
        plan: Dict[str, Any],
        inventory: Optional[Dict[str, Any]],
        quote: Optional[Dict[str, Any]],
        fulfillment: Optional[Dict[str, Any]],
    ) -> str:
        # Priority 1: Use fulfillment message if available, but also append
        # declined/out-of-stock item notes so no requested item is silently dropped.
        if fulfillment and fulfillment.get("customer_message"):
            base_message = fulfillment["customer_message"]

            declined_notes = []
            inv_lookup_all: Dict[str, Dict] = {}
            if inventory and inventory.get("lines"):
                inv_lookup_all = {
                    inv_line.get("item_name", "").lower(): inv_line
                    for inv_line in inventory["lines"]
                }

            if quote:
                all_quote_lines = quote.get("quote_lines", [])
                already_noted: set = set()
                # Backordered items are surfaced via the inventory fallback below with full pricing
                backordered_items_p1 = {
                    line.get("item_name", "").lower()
                    for line in all_quote_lines
                    if line.get("status", "").lower() == "backordered"
                }

                # Items explicitly declined by the quote agent
                for item_name in quote.get("declined_items", []):
                    if item_name.lower() in backordered_items_p1:
                        continue  # Will appear via inventory fallback with full restock + price info
                    inv_line = inv_lookup_all.get(item_name.lower(), {})
                    note = self._format_item_status_note(
                        item_name,
                        inv_line.get("requested_units", 0),
                        inv_line.get("available_units", 0),
                        inv_line.get("eta"),
                        all_quote_lines,
                    )
                    declined_notes.append(note)
                    already_noted.add(item_name.lower())

                # Quote lines with status 'insufficient', 'declined', or 'unavailable'
                for line in all_quote_lines:
                    if line.get("status", "").lower() in {"insufficient", "declined", "unavailable"}:
                        item_name = line.get("item_name", "item")
                        if item_name.lower() in already_noted:
                            continue
                        inv_line = inv_lookup_all.get(item_name.lower(), {})
                        note = self._format_item_status_note(
                            item_name,
                            inv_line.get("requested_units", line.get("quantity", 0)),
                            inv_line.get("available_units", 0),
                            inv_line.get("eta"),
                            all_quote_lines,
                        )
                        declined_notes.append(note)
                        already_noted.add(item_name.lower())

            # Also surface inventory lines for items not fulfilled that are insufficient
            if inventory and inventory.get("lines"):
                fulfilled_set = {
                    i.lower() for i in (fulfillment.get("fulfilled_items") or [])
                }
                already_noted_inv = {
                    d.lower().split(" is ")[0].split(" could")[0].split(" we ")[0]
                    for d in declined_notes
                }
                all_quote_lines_inv = (quote or {}).get("quote_lines", [])
                for inv_line in inventory["lines"]:
                    item_name = inv_line.get("item_name", "")
                    status = inv_line.get("status", "").lower()
                    if (
                        item_name.lower() not in fulfilled_set
                        and item_name.lower() not in already_noted_inv
                        and item_name.lower() not in backordered_items_p1
                        and status in {"insufficient", "unavailable", "out_of_stock"}
                    ):
                        note = self._format_item_status_note(
                            item_name,
                            inv_line.get("requested_units", 0),
                            inv_line.get("available_units", 0),
                            inv_line.get("eta"),
                            all_quote_lines_inv,
                        )
                        declined_notes.append(note)

            if declined_notes:
                return base_message + " Note: " + "; ".join(declined_notes) + "."
            return base_message
        
        #Priority 2: Build enhanced quote message
        if quote:
            message_parts = []
            quote_total = quote.get("total_amount", 0.0)
            
            if quote.get("quote_lines"):
                approved_lines = [line for line in quote["quote_lines"]
                                  if line.get("status", "").lower() in {"ready", "approved", "partial", "backordered"}]
                
                # Recalculate total from approved lines in case quote_total wasn't set (e.g. fully backordered)
                if approved_lines and quote_total == 0.0:
                    quote_total = round(sum(l.get("line_total", 0.0) for l in approved_lines), 2)

                if approved_lines and quote_total > 0:
                    # Calculate total quantity across all items
                    total_qty = sum(line.get('quantity', 0) for line in approved_lines)
                    
                    # Build main quote statement with item breakdown
                    if len(approved_lines) == 1:
                        line = approved_lines[0]
                        qty = line.get('quantity', 0)
                        unit_price = line.get('unit_price', 0)
                        item_name = line.get('item_name', 'item')
                        message_parts.append(
                            f"We can provide a quote of ${quote_total:.2f} for your request ({qty} units at ${unit_price:.2f} each)."
                        )
                    else:
                        message_parts.append(
                            f"We can provide a quote of ${quote_total:.2f} for your request ({total_qty} total units)."
                        )
                    
                    # Add itemized breakdown for multi-item orders
                    if len(approved_lines) > 1:
                        breakdown_parts = []
                        for line in approved_lines:
                            qty = line.get('quantity', 0)
                            item_name = line.get('item_name', 'item')
                            unit_price = line.get('unit_price', 0)
                            line_total = line.get('line_total', 0)
                            discount_pct = line.get('discount_pct', 0)
                            discount_info = f" ({discount_pct:.0f}% discount applied)" if discount_pct > 0 else ""
                            breakdown_parts.append(
                                f"{qty} units of {item_name} at ${unit_price:.2f} each = ${line_total:.2f}{discount_info}"
                            )
                        
                        if breakdown_parts:
                            message_parts.append("Breakdown: " + "; ".join(breakdown_parts) + ".")
                    
                    # Add inventory availability details with improved formatting
                    stock_status_parts = []
                    backorder_parts = []
                    if inventory and inventory.get("lines"):
                        # Build inventory lookup by item name
                        inv_lookup = {inv_line.get("item_name", "").lower(): inv_line 
                                    for inv_line in inventory["lines"]}
                        
                        for quote_line in approved_lines:
                            item_name = quote_line.get("item_name", "")
                            qty_requested = quote_line.get("quantity", 0)
                            quote_line_status = quote_line.get("status", "").lower()
                            inv_line = inv_lookup.get(item_name.lower())

                            if inv_line:
                                available = inv_line.get("available_units", 0)

                                if available >= qty_requested:
                                    stock_status_parts.append(
                                        f"{qty_requested} units of {item_name} available in stock"
                                    )
                                else:
                                    if available > 0:
                                        stock_status_parts.append(
                                            f"{available} units of {item_name} available in stock"
                                        )
                                        shortage = qty_requested - available
                                        if shortage > 0 and inv_line.get("eta"):
                                            backorder_parts.append(
                                                f"the remaining {shortage} units will arrive via supplier restock on {inv_line['eta']}"
                                            )
                                    else:
                                        if inv_line.get("eta"):
                                            backorder_parts.append(
                                                f"{qty_requested} units of {item_name} will arrive via supplier restock on {inv_line['eta']}"
                                            )
                                        else:
                                            # No ETA in inventory line — check quote line notes
                                            notes = quote_line.get("notes", "")
                                            if "restock expected by " in notes:
                                                eta_part = notes.split("restock expected by ")[-1].split(".")[0]
                                                backorder_parts.append(
                                                    f"{qty_requested} units of {item_name} will arrive via supplier restock on {eta_part}"
                                                )
                                            else:
                                                backorder_parts.append(
                                                    f"{qty_requested} units of {item_name} are on backorder (restock has been ordered)"
                                                )
                            elif quote_line_status == "backordered":
                                # No inventory line but we have a backordered quote line — extract ETA from notes
                                notes = quote_line.get("notes", "")
                                eta_part = ""
                                if "restock expected by " in notes:
                                    eta_part = notes.split("restock expected by ")[-1].split(".")[0]
                                if eta_part:
                                    backorder_parts.append(
                                        f"{qty_requested} units of {item_name} will arrive via supplier restock on {eta_part}"
                                    )
                                else:
                                    backorder_parts.append(
                                        f"{qty_requested} units of {item_name} are on backorder"
                                    )
                        
                        # Format stock status
                        if stock_status_parts:
                            if len(stock_status_parts) == 1:
                                message_parts.append(f"Currently {stock_status_parts[0]}.")
                            else:
                                message_parts.append("Currently " + ", ".join(stock_status_parts[:-1]) + 
                                                   f", and {stock_status_parts[-1]}.")
                        
                        # Format backorder status
                        if backorder_parts:
                            if len(backorder_parts) == 1:
                                message_parts.append(backorder_parts[0].capitalize() + ".")
                            else:
                                message_parts.append(
                                    backorder_parts[0].capitalize() + ", and " + 
                                    ", ".join(backorder_parts[1:]) + "."
                                )
                    
                    # Add delivery commitment
                    if backorder_parts:
                        message_parts.append("Once the restock arrives, we can complete the order and confirm delivery.")
                    elif stock_status_parts:
                        message_parts.append("We can ship immediately upon order confirmation.")
            
            # Include declined / insufficient items so no info is lost
            all_quote_lines = quote.get("quote_lines", [])
            # Items already shown in the main message as backordered — skip in notes
            backordered_items_p2 = {
                line.get("item_name", "").lower()
                for line in all_quote_lines
                if line.get("status", "").lower() == "backordered"
            }
            if quote.get("declined_items") or all_quote_lines:
                declined_notes_p2 = []
                already_noted_p2: set = set()
                inv_lookup_p2: Dict[str, Dict] = {}
                if inventory and inventory.get("lines"):
                    inv_lookup_p2 = {
                        il.get("item_name", "").lower(): il for il in inventory["lines"]
                    }
                for item_name in quote.get("declined_items", []):
                    if item_name.lower() in backordered_items_p2:
                        continue  # Already shown as backordered in the main message
                    inv_line = inv_lookup_p2.get(item_name.lower(), {})
                    note = self._format_item_status_note(
                        item_name,
                        inv_line.get("requested_units", 0),
                        inv_line.get("available_units", 0),
                        inv_line.get("eta"),
                        all_quote_lines,
                    )
                    declined_notes_p2.append(note)
                    already_noted_p2.add(item_name.lower())
                for line in all_quote_lines:
                    if line.get("status", "").lower() in {"insufficient", "declined", "unavailable"}:
                        item_name = line.get("item_name", "item")
                        if item_name.lower() in already_noted_p2 or item_name.lower() in backordered_items_p2:
                            continue
                        inv_line = inv_lookup_p2.get(item_name.lower(), {})
                        note = self._format_item_status_note(
                            item_name,
                            inv_line.get("requested_units", line.get("quantity", 0)),
                            inv_line.get("available_units", 0),
                            inv_line.get("eta"),
                            all_quote_lines,
                        )
                        declined_notes_p2.append(note)
                        already_noted_p2.add(item_name.lower())
                if declined_notes_p2:
                    message_parts.append("Note: " + "; ".join(declined_notes_p2) + ".")
            
            # If we built a message, return it
            if message_parts:
                return " ".join(message_parts)
            
            # CRITICAL FALLBACK: Use quote_explanation to avoid empty strings
            if quote.get("quote_explanation"):
                explanation = quote["quote_explanation"]
                if quote_total > 0:
                    return f"{explanation} Total quoted amount: ${quote_total:.2f}."
                return explanation
        
        # Priority 2b: No quote but inventory has useful info — include full detail
        if inventory and inventory.get("lines"):
            inv_parts = []
            for inv_line in inventory["lines"]:
                item_name = inv_line.get("item_name", "item")
                status = inv_line.get("status", "").lower()
                available = inv_line.get("available_units", 0)
                requested = inv_line.get("requested_units", 0)
                eta = inv_line.get("eta")
                if status in {"ready", "available"}:
                    inv_parts.append(f"{item_name} is available ({available} units in stock)")
                elif status in {"partial", "insufficient"}:
                    inv_parts.append(
                        self._format_item_status_note(item_name, requested, available, eta)
                    )
            if inv_parts:
                return " ".join(inv_parts)
        
        # Priority 3: Use inventory notes
        if inventory and inventory.get("decision_notes"):
            return inventory["decision_notes"]
        
        # Priority 4: Final fallback
        return f"We received your request for the {payload.get('event', 'your event')} and will follow up with a quote shortly."


# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():
    """This function runs a series of test scenarios against the Beaver's Choice system."""

    print(f"{C.HEADER}Initializing Database...{C.RESET}")
    init_database(db_engine)
    try:
        quote_requests_sample = pd.read_csv("files/quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"{C.WARN}[FATAL] Error loading test data: {e}{C.RESET}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]
    # initializing the multi-agent system
    system = BeaverChoiceSystem()

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n{C.HEADER}=== Request {idx+1} ==={C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Context: {row['job']} organizing {row['event']}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Request Date: {request_date}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Request: {row['request']}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Cash Balance: ${current_cash:.2f}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Inventory Value: ${current_inventory:.2f}{C.RESET}")

        # Process request
        request_payload = row.to_dict()
        request_payload["request_date"] = row["request_date"]

        # Use system to process the request and generate a response
        agent_result = system.process_request(request_payload)
        response = agent_result.get("customer_message", "No response generated.")

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        qt = agent_result.get("quote_total", 0.0)
        print(f"{C.QUOTE}[Quote Engineer] Quote Total: ${qt:.2f}{C.RESET}")
        print(f"{C.FULFIL}[Fulfillment Agent] Response: {response}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Updated Cash: ${current_cash:.2f}{C.RESET}")
        print(f"{C.ORCH}[Paper Factory Orchestrator] Updated Inventory: ${current_inventory:.2f}{C.RESET}")

        items_immediately_available = agent_result.get("items_immediately_available", [])
        items_pending_on_restock = agent_result.get("items_pending_on_restock", [])
        items_not_available = agent_result.get("items_not_available", [])
        print(f"{C.INV}[Stock Agent] Items immediately available: {items_immediately_available}{C.RESET}")
        print(f"{C.INV}[Stock Agent] Items pending restock: {items_pending_on_restock}{C.RESET}")
        print(f"{C.WARN}[Stock Agent] Items not available (uncataloged): {items_not_available}{C.RESET}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": round(current_cash, 1),
                "inventory_value": round(current_inventory, 1),
                "quote_total": agent_result.get("quote_total", 0.0),
                "items_immediately_available": ", ".join(f"{k} ({v})" for k, v in items_immediately_available.items()),
                "items_pending_on_restock": ", ".join(
                    f"{k} ({v['quantity']} units, expected {v['eta']})" if isinstance(v, dict) else f"{k} ({v})"
                    for k, v in items_pending_on_restock.items()
                ),
                "items_not_available": ", ".join(items_not_available),
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print(f"\n{C.HEADER}===== FINAL FINANCIAL REPORT ====={C.RESET}")
    print(f"{C.HEADER}Final Cash: ${final_report['cash_balance']:.2f}{C.RESET}")
    print(f"{C.HEADER}Final Inventory: ${final_report['inventory_value']:.2f}{C.RESET}")

    # Save results
    pd.DataFrame(results).to_csv("files/test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()
