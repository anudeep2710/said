from flask import Flask, render_template, request, jsonify
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.utils
import json
import os
import requests
from datetime import datetime, timedelta
from huggingface_hub import InferenceClient
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Hugging Face configuration
HF_TOKEN = os.getenv("HUGGING_FACE_TOKEN", "your_token_here")  # Use environment variable
API_URL = "https://api-inference.huggingface.co/models/tabularisai/augini"
headers = {"Authorization": f"Bearer {HF_TOKEN}"}

# Initialize inventory and sales data
inventory_data = [
    {"id": 1, "product": "Laptop", "category": "Electronics", "price": 50000, "quantity": 50, "min_quantity": 10},
    {"id": 2, "product": "Smartphone", "category": "Electronics", "price": 30000, "quantity": 100, "min_quantity": 20},
    {"id": 3, "product": "Headphones", "category": "Electronics", "price": 10000, "quantity": 200, "min_quantity": 30}
]

sales_data = []

def save_sale(product_id, quantity, price):
    sale = {
        "product_id": product_id,
        "product": next(item["product"] for item in inventory_data if item["id"] == product_id),
        "quantity": quantity,
        "price": price,
        "total": quantity * price,
        "timestamp": datetime.now().isoformat()
    }
    sales_data.append(sale)
    return sale

def get_daily_sales():
    today = datetime.now().date()
    return [sale for sale in sales_data if datetime.fromisoformat(sale["timestamp"]).date() == today]

def get_monthly_sales():
    current_month = datetime.now().month
    return [sale for sale in sales_data if datetime.fromisoformat(sale["timestamp"]).month == current_month]

def generate_insights():
    # Initialize default insights
    insights = {
        'top_products': {},
        'revenue_trend': {},
        'category_performance': []
    }

    try:
        if sales_data:
            # Top selling products
            sales_df = pd.DataFrame(sales_data)
            top_products = sales_df.groupby('product')['quantity'].sum().sort_values(ascending=False).head(3)
            insights['top_products'] = top_products.to_dict()

            # Revenue trend
            sales_df['date'] = pd.to_datetime(sales_df['timestamp']).dt.date
            revenue_trend = sales_df.groupby('date')['total'].sum()
            # Convert date to string for JSON serialization
            insights['revenue_trend'] = {str(k): v for k, v in revenue_trend.to_dict().items()}

        # Category performance
        inventory_df = pd.DataFrame(inventory_data)
        category_performance = inventory_df.groupby('category').agg({
            'quantity': 'sum',
            'price': 'mean'
        }).reset_index()
        insights['category_performance'] = category_performance.to_dict('records')

    except Exception as e:
        print(f"Error generating insights: {str(e)}")

    return insights

def generate_charts():
    # Initialize default charts
    empty_fig = px.bar(title='No data available')
    charts = {
        'top_products': json.dumps(empty_fig, cls=plotly.utils.PlotlyJSONEncoder),
        'revenue_trend': json.dumps(empty_fig, cls=plotly.utils.PlotlyJSONEncoder)
    }

    try:
        if sales_data:
            # Top products chart
            sales_df = pd.DataFrame(sales_data)
            top_products = sales_df.groupby('product')['quantity'].sum().sort_values(ascending=False).head(3)
            top_products_fig = px.bar(
                top_products.reset_index(),
                x='product',
                y='quantity',
                title='Top Selling Products'
            )
            charts['top_products'] = json.dumps(top_products_fig, cls=plotly.utils.PlotlyJSONEncoder)

            # Revenue trend chart
            sales_df['date'] = pd.to_datetime(sales_df['timestamp']).dt.date
            revenue_trend = sales_df.groupby('date')['total'].sum()
            revenue_trend_fig = px.line(
                revenue_trend.reset_index(),
                x='date',
                y='total',
                title='Revenue Trend'
            )
            charts['revenue_trend'] = json.dumps(revenue_trend_fig, cls=plotly.utils.PlotlyJSONEncoder)

    except Exception as e:
        print(f"Error generating charts: {str(e)}")

    return charts

def query_huggingface(payload):
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error from Hugging Face API: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error querying Hugging Face: {str(e)}")
        return None

@app.route('/')
def index():
    insights = generate_insights()
    charts = generate_charts()
    return render_template('index.html',
                         inventory=inventory_data,
                         daily_sales=get_daily_sales(),
                         monthly_sales=get_monthly_sales(),
                         insights=insights,
                         charts=charts)

@app.route('/api/inventory', methods=['GET', 'POST', 'DELETE'])
def manage_inventory():
    if request.method == 'GET':
        return jsonify(inventory_data)

    data = request.json
    if request.method == 'POST':
        if 'id' in data:  # Update existing item
            for item in inventory_data:
                if item['id'] == data['id']:
                    item.update(data)
                    break
        else:  # Add new item
            new_id = max(item['id'] for item in inventory_data) + 1 if inventory_data else 1
            data['id'] = new_id
            inventory_data.append(data)
        return jsonify({"success": True})

    if request.method == 'DELETE':
        inventory_data[:] = [item for item in inventory_data if item['id'] != data['id']]
        return jsonify({"success": True})

@app.route('/api/sales', methods=['POST'])
def record_sale():
    data = request.json
    product_id = data['product_id']
    quantity = data['quantity']

    # Find the product
    product = next(item for item in inventory_data if item['id'] == product_id)

    if product['quantity'] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    # Update inventory
    product['quantity'] -= quantity

    # Record sale
    sale = save_sale(product_id, quantity, product['price'])

    return jsonify({
        "success": True,
        "sale": sale,
        "inventory": inventory_data
    })

@app.route('/api/analyze', methods=['POST'])
def analyze():
    question = request.json.get('question', '')

    # Prepare data for Hugging Face
    data_payload = {
        "inputs": {
            "question": question,
            "context": {
                "inventory": inventory_data,
                "sales": sales_data
            },
            "parameters": {
                "temperature": 0.7,
            }
        }
    }

    try:
        result = query_huggingface(data_payload)
        return jsonify({
            "answer": result if result else "I don't have enough information to answer that question.",
            "insights": generate_insights(),
            "charts": generate_charts()
        })
    except Exception as e:
        print(f"Error analyzing: {str(e)}")
        return jsonify({
            "answer": "An error occurred while analyzing the data.",
            "insights": generate_insights(),
            "charts": generate_charts()
        })

# BizzyBuddy specific API endpoints
@app.route('/api/bizzybuddy/inventory', methods=['GET'])
def get_bizzybuddy_inventory():
    # Convert inventory data to BizzyBuddy format
    bizzybuddy_inventory = []
    for item in inventory_data:
        bizzybuddy_item = {
            "id": str(item['id']),
            "name": item['product'],
            "description": f"{item['category']} product",
            "price": item['price'],
            "stockQuantity": item['quantity'],
            "category": item['category'],
            "createdAt": datetime.now().isoformat(),
            "updatedAt": datetime.now().isoformat(),
            "imageUrl": None,
            "attributes": {}
        }
        bizzybuddy_inventory.append(bizzybuddy_item)

    return jsonify(bizzybuddy_inventory)

@app.route('/api/bizzybuddy/sales', methods=['GET'])
def get_bizzybuddy_sales():
    # Convert sales data to BizzyBuddy format
    bizzybuddy_sales = []
    for sale in sales_data:
        bizzybuddy_sale = {
            "id": f"sale_{len(bizzybuddy_sales) + 1}",
            "productId": str(sale['product_id']),
            "quantity": sale['quantity'],
            "unitPrice": sale['price'],
            "totalAmount": sale['total'],
            "date": sale['timestamp']
        }
        bizzybuddy_sales.append(bizzybuddy_sale)

    return jsonify(bizzybuddy_sales)

@app.route('/api/bizzybuddy/analytics', methods=['GET'])
def get_bizzybuddy_analytics():
    insights = generate_insights()
    charts = generate_charts()

    analytics_data = {
        "salesSummary": {
            "daily": sum(sale['total'] for sale in get_daily_sales()),
            "weekly": sum(sale['total'] for sale in sales_data if datetime.fromisoformat(sale['timestamp']) > (datetime.now() - timedelta(days=7))),
            "monthly": sum(sale['total'] for sale in get_monthly_sales())
        },
        "topProducts": insights['top_products'],
        "categoryPerformance": insights['category_performance'],
        "revenueTrend": insights['revenue_trend']
    }

    return jsonify(analytics_data)

@app.route('/api/bizzybuddy/record-sale', methods=['POST'])
def record_bizzybuddy_sale():
    data = request.json

    # Check if required fields exist and are not None
    if not data:
        return jsonify({"error": "Missing request body"}), 400

    if 'productId' not in data or data.get('productId') is None:
        return jsonify({"error": "Missing or invalid productId parameter"}), 400

    if 'quantity' not in data or data.get('quantity') is None:
        return jsonify({"error": "Missing or invalid quantity parameter"}), 400

    try:
        product_id = int(data.get('productId'))
        quantity = int(data.get('quantity'))
    except (ValueError, TypeError):
        return jsonify({"error": "productId and quantity must be valid integers"}), 400

    # Find the product
    product = next((item for item in inventory_data if item['id'] == product_id), None)

    if not product:
        return jsonify({"error": "Product not found"}), 404

    if product['quantity'] < quantity:
        return jsonify({"error": "Insufficient stock"}), 400

    # Update inventory
    product['quantity'] -= quantity

    # Record sale
    sale = save_sale(product_id, quantity, product['price'])

    return jsonify({
        "success": True,
        "sale": sale,
        "inventory": [item for item in inventory_data if item['id'] == product_id]
    })

# Route to serve the BizzyBuddy test page
@app.route('/bizzybuddy-test')
def bizzybuddy_test():
    return render_template('bizzybuddy_test.html')

if __name__ == '__main__':
    app.run(debug=True, port=5002, host='0.0.0.0')