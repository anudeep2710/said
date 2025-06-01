@app.route('/api/bizzybuddy/record-sale', methods=['POST'])
def record_bizzybuddy_sale():
    data = request.json
    
    # Check if required fields exist and are not None
    if not data or 'productId' not in data or data['productId'] is None:
        return jsonify({"error": "Missing or invalid productId parameter"}), 400
        
    if not data or 'quantity' not in data or data['quantity'] is None:
        return jsonify({"error": "Missing or invalid quantity parameter"}), 400
    
    try:
        product_id = int(data.get('productId'))
        quantity = int(data.get('quantity'))
    except (ValueError, TypeError):
        return jsonify({"error": "productId and quantity must be valid numbers"}), 400
    
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