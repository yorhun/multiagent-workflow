#!/usr/bin/env python3
"""
Generate the Beaver's Choice multi-agent workflow diagram.
Run from the project root: python docs/generate_workflow_diagram.py
Outputs: docs/beavers_choice_workflow.png
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

# ── canvas ────────────────────────────────────────────────────────────────────
FW, FH, DPI = 26, 19, 110
fig, ax = plt.subplots(figsize=(FW, FH), dpi=DPI)
ax.set_xlim(0, FW)
ax.set_ylim(0, FH)
ax.axis('off')
BG = '#F4F6FA'
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)

# ── colour palette ────────────────────────────────────────────────────────────
#  Each entry: (face, edge_accent, header_bg, header_text, body_text)
PAL = {
    'customer':     ('#FFF8F0', '#E65100', '#E65100', '#FFFFFF', '#3E2723'),
    'orchestrator': ('#EBF3FF', '#1A73E8', '#1A73E8', '#FFFFFF', '#0D1B2A'),
    'stockagent':     ('#FFFEF0', '#F9A825', '#F9A825', '#FFFFFF', '#212121'),
    'quote':        ('#FAF0FF', '#8E24AA', '#8E24AA', '#FFFFFF', '#212121'),
    'fulfillment':  ('#F0FFF2', '#2E7D32', '#2E7D32', '#FFFFFF', '#212121'),
    'db':           ('#E8FAFB', '#00838F', '#00838F', '#FFFFFF', '#003333'),
    'response':     ('#FFFFF0', '#D4A017', '#D4A017', '#FFFFFF', '#3E2723'),
}
TOOL_PAL = {
    'stockagent':    ('#FFFEF8', '#F9A825'),
    'quote':       ('#FDF5FF', '#8E24AA'),
    'fulfillment': ('#F5FFF6', '#2E7D32'),
}
ARROW_C  = '#37474F'
DASH_C   = '#78909C'
LABEL_C  = '#37474F'


# ── drawing helpers ───────────────────────────────────────────────────────────

def rbox(x0, y0, w, h, face, edge, lw=2.2, r=0.22, zorder=2, alpha=1.0):
    p = FancyBboxPatch(
        (x0, y0), w, h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=lw, edgecolor=edge, facecolor=face,
        zorder=zorder, alpha=alpha,
    )
    ax.add_patch(p)


def agent_box(x0, y0, w, h, title, face, edge, hdr_h=0.65, lw=2.5, r=0.22, zorder=2):
    """Rounded rect with solid coloured header stripe."""
    # body
    rbox(x0, y0, w, h, face, edge, lw=lw, r=r, zorder=zorder)
    # header solid fill (slightly smaller so rounded corners show)
    hdr_rect = mpatches.FancyBboxPatch(
        (x0 + lw/100, y0 + h - hdr_h), w - lw/50, hdr_h,
        boxstyle=f"round,pad=0,rounding_size={r}",
        linewidth=0, facecolor=edge, zorder=zorder + 1,
    )
    ax.add_patch(hdr_rect)
    # square off the bottom half of header so it blends into body
    sq = mpatches.Rectangle(
        (x0 + lw/100, y0 + h - hdr_h), w - lw/50, hdr_h / 2,
        color=edge, zorder=zorder + 1,
    )
    ax.add_patch(sq)
    ax.text(
        x0 + w / 2, y0 + h - hdr_h / 2,
        title, ha='center', va='center',
        fontsize=11.5, fontweight='bold', color='white', zorder=zorder + 2,
    )


def T(x, y, s, size=9, color='#212121', ha='left', va='top',
      style='normal', weight='normal', z=6, family=None):
    kwargs = dict(ha=ha, va=va, fontsize=size, color=color,
                  fontstyle=style, fontweight=weight, zorder=z)
    if family:
        kwargs['family'] = family
    ax.text(x, y, s, **kwargs)


def bullet_lines(x, y, lines, size=8.8, color='#2C2C2C', gap=0.35):
    for line in lines:
        T(x, y, f"• {line}", size=size, color=color)
        y -= gap
    return y


def arr(x0, y0, x1, y1, label='', lw=2, color=ARROW_C, dashed=False,
        rad=0.0, label_dx=0.12, label_dy=0.12):
    style = 'dashed' if dashed else 'solid'
    conn = f'arc3,rad={rad}'
    ax.annotate(
        '', xy=(x1, y1), xytext=(x0, y0),
        arrowprops=dict(
            arrowstyle='->', color=color, lw=lw,
            connectionstyle=conn, linestyle=style,
        ),
        zorder=8,
    )
    if label:
        mx = (x0 + x1) / 2 + label_dx
        my = (y0 + y1) / 2 + label_dy
        ax.text(mx, my, label, fontsize=8, color=color,
                ha='left', va='bottom', style='italic', zorder=9,
                bbox=dict(boxstyle='round,pad=0.15', fc=BG, ec='none', alpha=0.85))


def tool_block(x0, y0, w, h, name, helper_fn, desc, agent_key, z=5):
    face, edge = TOOL_PAL[agent_key]
    rbox(x0, y0, w, h, face, edge, lw=1.6, r=0.16, zorder=z)
    # name
    ax.text(x0 + 0.18, y0 + h - 0.22, name,
            ha='left', va='top', fontsize=9, fontweight='bold',
            color=edge, zorder=z + 1)
    # helper function
    ax.text(x0 + 0.18, y0 + h - 0.60, helper_fn,
            ha='left', va='top', fontsize=8, color='#455A64',
            fontstyle='italic', family='monospace', zorder=z + 1)
    # description
    # wrap long descriptions manually
    lines = _wrap(desc, 44)
    ty = y0 + h - 0.97
    for ln in lines:
        ax.text(x0 + 0.18, ty, ln,
                ha='left', va='top', fontsize=8, color='#424242', zorder=z + 1)
        ty -= 0.30


def _wrap(text, width):
    """Simple word-wrap."""
    words = text.split()
    lines, cur = [], ''
    for w in words:
        if len(cur) + len(w) + 1 > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = (cur + ' ' + w).strip()
    if cur:
        lines.append(cur)
    return lines


# ═══════════════════════════════════════════════════════════════════════════════
# LAYOUT CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Column x-ranges  [x0, x1]
COL = {
    'stockagent':    (0.35,  8.3),
    'quote':       (8.75, 16.7),
    'fulfillment': (17.15, 25.65),
}
CW = COL['stockagent'][1] - COL['stockagent'][0]   # column width ~7.95

# Row y-ranges
R_TITLE   = (18.0, 18.8)
R_TOP     = (14.6, 17.5)   # customer / orchestrator / response
R_AGENT   = (11.0, 14.3)   # agent boxes
R_TOOLS   = (2.9,  10.7)   # tool blocks
R_DB      = (0.35,  2.6)   # SQLite db

TOOL_H    = 2.24            # height of each tool block
TOOL_GAP  = 0.22


# ═══════════════════════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════════════════════
ax.text(FW / 2, 18.55,
        "Beaver's Choice — Multi-Agent Orchestration Workflow",
        ha='center', va='center', fontsize=16, fontweight='bold',
        color='#1A237E', zorder=10)
ax.text(FW / 2, 18.1,
        "project_starter.py  ·  pydantic-ai  ·  SQLite",
        ha='center', va='center', fontsize=10, color='#546E7A', zorder=10)


# ═══════════════════════════════════════════════════════════════════════════════
# TOP ROW  —  Customer | Orchestrator | Final Response
# ═══════════════════════════════════════════════════════════════════════════════

# Customer box
cx0, cx1 = 0.35, 4.1
cy0, cy1 = 14.85, 17.2
agent_box(cx0, cy0, cx1 - cx0, cy1 - cy0,
          'Customer Request', *PAL['customer'][:2])
bullet_lines(cx0 + 0.2, cy1 - 0.85, [
    'Request text + metadata',
    'job, event, due date',
    'quote_requests_sample.csv',
], size=8.5, color=PAL['customer'][4])

# Orchestrator box
ox0, ox1 = 4.6, 21.3
oy0, oy1 = 14.6, 17.5
agent_box(ox0, oy0, ox1 - ox0, oy1 - oy0,
          'Paper Factory Orchestrator  (pydantic-ai Agent)', *PAL['orchestrator'][:2], hdr_h=0.68)
bullet_lines(ox0 + 0.25, oy1 - 0.88, [
    'Receives customer request  ·  Canonicalises product names  ·  Determines due date & priority',
    'Delegates sequentially: run_inventory_agent → run_quote_agent → run_fulfillment_agent',
    'Collects structured JSON outputs from each worker  ·  Composes FinalOrchestratorOutput',
    'Output schema: { customer_message, quote_total, fulfilled_items }',
], size=8.8, color=PAL['orchestrator'][4])

# Final Response box
rx0, rx1 = 21.55, 25.65
ry0, ry1 = 14.85, 17.4
agent_box(rx0, ry0, rx1 - rx0, ry1 - ry0,
          'Final Response', *PAL['response'][:2])
bullet_lines(rx0 + 0.2, ry1 - 0.85, [
    'customer_message',
    'quote_total ($)',
    'fulfilled_items [ ]',
    'items_immediately_avail.',
    'items_pending_restock',
], size=8.5, color=PAL['response'][4])


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT BOXES  (middle row)
# ═══════════════════════════════════════════════════════════════════════════════

AGENTS = [
    ('stockagent',    'Stock Agent',      PAL['stockagent']),
    ('quote',       'Quote Engineer',      PAL['quote']),
    ('fulfillment', 'Fulfillment Agent',  PAL['fulfillment']),
]

AGENT_BULLETS = {
    'stockagent': [
        'Checks inventory for requested items',
        'Initiates supplier restock orders',
        'Respects cash budget & delivery windows',
        'Output: InventoryAssessment JSON',
    ],
    'quote': [
        'Looks up comparable historical quotes',
        'Verifies available cash before pricing',
        'Builds itemised quote with markup & discount',
        'Output: QuoteDecision JSON',
    ],
    'fulfillment': [
        'Runs financial snapshot for context',
        'Sales already recorded in quote pipeline',
        'Generates final customer-facing message',
        'Output: FulfillmentSummary JSON',
    ],
}

for key, title, pal in AGENTS:
    x0, x1 = COL[key]
    y0, y1 = R_AGENT
    agent_box(x0, y0, x1 - x0, y1 - y0, title, *pal[:2], hdr_h=0.62)
    bullet_lines(x0 + 0.22, y1 - 0.80, AGENT_BULLETS[key],
                 size=8.6, color=pal[4])


# ═══════════════════════════════════════════════════════════════════════════════
# TOOL BLOCKS
# ═══════════════════════════════════════════════════════════════════════════════

TOOLS = {
    'stockagent': [
        (
            'tool_inventory_snapshot',
            '→ get_all_inventory(as_of_date)',
            'Queries transactions table; returns dict of {item: stock} '
            'for all items with positive inventory as of the given date.',
        ),
        (
            'tool_item_stock_probe',
            '→ get_stock_level(item_name, as_of_date)',
            'Single-item stock check: sums stock_orders minus sales '
            'up to the given date. Canonicalises item name first.',
        ),
        (
            'tool_plan_restock_purchase',
            '→ get_supplier_delivery_date(date, qty)\n   + create_transaction(..., "stock_orders")',
            'Checks cash budget, calls get_supplier_delivery_date for '
            'lead time, then logs a stock_orders transaction via '
            'create_transaction. Defers if cost > 85 % of cash.',
        ),
    ],
    'quote': [
        (
            'tool_lookup_quote_history',
            '→ search_quote_history(terms, limit=5)',
            'SQL LIKE join on quote_requests + quotes tables. '
            'Returns up to 5 matching past quotes sorted by recency '
            'to inform pricing decisions.',
        ),
        (
            'tool_cash_window',
            '→ get_cash_balance(as_of_date)',
            'Computes net cash: total sales revenue minus total '
            'stock_orders cost up to the given date.',
        ),
        (
            'tool_price_builder',
            '→ volume markup + discount math (inline)',
            'Applies volume markup (28 % / 18 % / 12 %), caps discount '
            'at 15 %, adds 2 % rush fee if expedited. Returns unit_price '
            'and line_total.',
        ),
    ],
    'fulfillment': [
        (
            'tool_financial_snapshot',
            '→ generate_financial_report(as_of_date)',
            'Returns cash_balance, inventory_value, total_assets, '
            'itemised inventory, and top-5 revenue products. Used to '
            'frame the customer message without exposing raw figures.',
        ),
        (
            'tool_record_sale  [pipeline step]',
            '→ create_transaction(item, "sales", qty, price, date)',
            'Called directly in run_quote_agent for every ready/partial '
            'quote line before Fulfillment Ranger runs. Inserts a sales '
            'row in the transactions table and returns the row ID.',
        ),
    ],
}

# Tool section header label
for key, _, pal in AGENTS:
    x0, x1 = COL[key]
    tx = (x0 + x1) / 2
    ax.text(tx, R_TOOLS[1] + 0.18, 'Tools & Helper Functions',
            ha='center', va='bottom', fontsize=9.5, fontweight='bold',
            color=pal[2], zorder=7,
            bbox=dict(boxstyle='round,pad=0.18', fc=BG, ec='none'))

for key, _, pal in AGENTS:
    x0, x1 = COL[key]
    tools = TOOLS[key]
    n = len(tools)
    total_h = n * TOOL_H + (n - 1) * TOOL_GAP
    ty_top = R_TOOLS[1]   # start from top of tool zone

    for i, (tname, tfn, tdesc) in enumerate(tools):
        tb_y1 = ty_top - i * (TOOL_H + TOOL_GAP)
        tb_y0 = tb_y1 - TOOL_H
        tool_block(x0, tb_y0, x1 - x0, TOOL_H, tname, tfn, tdesc, key)


# ═══════════════════════════════════════════════════════════════════════════════
# SQLite DATABASE ROW
# ═══════════════════════════════════════════════════════════════════════════════
db_x0, db_x1 = 0.35, 25.65
db_y0, db_y1 = R_DB
agent_box(db_x0, db_y0, db_x1 - db_x0, db_y1 - db_y0,
          'SQLite Database  (munder_difflin.db)', *PAL['db'][:2], hdr_h=0.58)

# Four table columns inside DB box
tables = [
    ('transactions',
     'id · item_name · transaction_type\nunits · price · transaction_date · delivery_date'),
    ('quote_requests',
     'id · response · job · event\nrequest_date · due_date'),
    ('quotes',
     'request_id · total_amount · quote_explanation\njob_type · order_size · event_type'),
    ('inventory',
     'item_name · category · unit_price\ncurrent_stock · min_stock_level'),
]
ncols = len(tables)
db_inner_w = (db_x1 - db_x0 - 0.4) / ncols
for i, (tname, tfields) in enumerate(tables):
    tx0 = db_x0 + 0.2 + i * db_inner_w
    tx1 = tx0 + db_inner_w - 0.15
    ty0 = db_y0 + 0.12
    ty1 = db_y1 - 0.65
    rbox(tx0, ty0, tx1 - tx0, ty1 - ty0,
         face='#FFFFFF', edge=PAL['db'][1], lw=1.2, r=0.12, zorder=4)
    ax.text((tx0 + tx1) / 2, ty1 - 0.12, tname,
            ha='center', va='top', fontsize=9, fontweight='bold',
            color=PAL['db'][2], zorder=5)
    for j, fl in enumerate(tfields.split('\n')):
        ax.text(tx0 + 0.12, ty1 - 0.42 - j * 0.30, fl,
                ha='left', va='top', fontsize=7.8, color='#37474F',
                family='monospace', zorder=5)


# ═══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ═══════════════════════════════════════════════════════════════════════════════

# 1. Customer → Orchestrator
arr(cx1, (cy0 + cy1) / 2, ox0, (oy0 + oy1) / 2,
    lw=2.2, color='#E65100')

# 2. Orchestrator → Final Response
arr(ox1, (oy0 + oy1) / 2, rx0, (ry0 + ry1) / 2,
    lw=2.2, color='#1A73E8')

# 3. Orchestrator → each agent (delegation, going down)
orch_mid_y = oy0   # bottom of orchestrator box
agent_row_top = R_AGENT[1]

def orch_to_agent(key, rad=0.0):
    ax0, ax1 = COL[key]
    agent_cx = (ax0 + ax1) / 2
    src_x = max(ox0 + 0.5, min(ox1 - 0.5, agent_cx))
    arr(src_x, orch_mid_y, agent_cx, agent_row_top,
        lw=2, color='#1A73E8', rad=rad)

orch_to_agent('stockagent',    rad=-0.15)
orch_to_agent('quote',       rad=0.0)
orch_to_agent('fulfillment', rad=0.15)

# 4. Agent → Orchestrator (return result, dashed)
def agent_to_orch(key, rad=0.0):
    ax0, ax1 = COL[key]
    agent_cx = (ax0 + ax1) / 2 + 0.5
    src_x = max(ox0 + 0.5, min(ox1 - 0.5, agent_cx + 0.5))
    arr(agent_cx, agent_row_top + 0.05, src_x, orch_mid_y - 0.05,
        lw=1.5, color=DASH_C, dashed=True, rad=rad)

agent_to_orch('stockagent',    rad=0.18)
agent_to_orch('quote',       rad=0.0)
agent_to_orch('fulfillment', rad=-0.18)

# 5. Agent → tool section (short connector line)
for key, _, pal in AGENTS:
    ax0, ax1 = COL[key]
    agent_cx = (ax0 + ax1) / 2
    arr(agent_cx, R_AGENT[0], agent_cx, R_TOOLS[1] + 0.05,
        lw=1.8, color=pal[2])

# 6. Tools → SQLite DB (one arrow per column)
db_top = db_y1
for key, _, pal in AGENTS:
    ax0, ax1 = COL[key]
    agent_cx = (ax0 + ax1) / 2
    tb_bottom = R_TOOLS[1] - len(TOOLS[key]) * (TOOL_H + TOOL_GAP) + TOOL_GAP
    arr(agent_cx, R_TOOLS[0], agent_cx, db_top,
        lw=1.6, color=pal[2], dashed=False)


# ═══════════════════════════════════════════════════════════════════════════════
# LEGEND
# ═══════════════════════════════════════════════════════════════════════════════
legend_x, legend_y = 17.2, 11.8   # inside fulfillment agent area — no, put it outside
# Actually place legend below the diagram title area (top-right blank space)
# Let me check if there's space... not much. Put it in an overlay box in top-right area.
# There's a small gap between orch box right edge and diagram right edge.
# Actually we have the response box there. Let's skip a formal legend
# and instead just annotate the arrow types directly on the figure.

legend_items = [
    (ARROW_C,  '-',  'Orchestration / delegation (solid)'),
    (DASH_C,   '--', 'Result return (dashed)'),
    (PAL['stockagent'][2],    '-',  'Stock Agent data flow'),
    (PAL['quote'][2],       '-',  'Quote Engineer data flow'),
    (PAL['fulfillment'][2], '-',  'Fulfillment Agent data flow'),
]

leg_x0, leg_y0 = 0.4, 17.55
for i, (clr, ls, label) in enumerate(legend_items):
    lx = leg_x0 + i * 4.6
    ly = leg_y0
    # draw mini line
    ax.plot([lx, lx + 0.5], [ly + 0.12, ly + 0.12],
            color=clr, lw=2, linestyle='dashed' if ls == '--' else 'solid',
            zorder=9)
    ax.text(lx + 0.65, ly + 0.12, label,
            va='center', fontsize=7.8, color='#37474F', zorder=9)


# ── save ─────────────────────────────────────────────────────────────────────
Path('docs').mkdir(exist_ok=True)
out = Path('docs') / 'beavers_choice_workflow.png'
plt.savefig(out, dpi=DPI, bbox_inches='tight', facecolor=BG)
print(f"Saved → {out}")
