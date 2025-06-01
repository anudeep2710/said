const express = require('express');
const multer = require('multer');
const cors = require('cors');
const { Client } = require('@gradio/client');
const path = require('path');
require('dotenv').config();

const app = express();
const upload = multer({ dest: 'uploads/' });

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Initialize Hugging Face client
let client;
(async () => {
    try {
        client = await Client.connect("tabularisai/augini");
        console.log("Connected to Hugging Face model successfully");
    } catch (error) {
        console.error("Error connecting to Hugging Face model:", error);
    }
})();

// Sample data for testing
const sampleData = [
    { product: "Laptop", sales: 150, revenue: 750000, category: "Electronics", month: "January" },
    { product: "Smartphone", sales: 300, revenue: 900000, category: "Electronics", month: "January" },
    { product: "Headphones", sales: 200, revenue: 200000, category: "Electronics", month: "January" },
    { product: "Laptop", sales: 180, revenue: 900000, category: "Electronics", month: "February" },
    { product: "Smartphone", sales: 350, revenue: 1050000, category: "Electronics", month: "February" },
    { product: "Headphones", sales: 250, revenue: 250000, category: "Electronics", month: "February" }
];

// Routes
app.get('/api/sample-data', (req, res) => {
    res.json(sampleData);
});

app.post('/api/analyze', async (req, res) => {
    try {
        const { question } = req.body;
        
        // Get analysis from Hugging Face model
        const result = await client.predict("/chat_with_data", {
            message: question,
            history: []
        });

        res.json({
            answer: result.data[1],
            insights: generateInsights(sampleData)
        });
    } catch (error) {
        console.error("Error in analysis:", error);
        res.status(500).json({ error: "Error processing your request" });
    }
});

// Helper function to generate insights
function generateInsights(data) {
    const insights = {
        topSelling: findTopSelling(data),
        revenueTrend: calculateRevenueTrend(data),
        categoryPerformance: analyzeCategoryPerformance(data)
    };
    return insights;
}

function findTopSelling(data) {
    const productSales = {};
    data.forEach(item => {
        if (!productSales[item.product]) {
            productSales[item.product] = 0;
        }
        productSales[item.product] += item.sales;
    });
    
    return Object.entries(productSales)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 3)
        .map(([product, sales]) => ({ product, sales }));
}

function calculateRevenueTrend(data) {
    const monthlyRevenue = {};
    data.forEach(item => {
        if (!monthlyRevenue[item.month]) {
            monthlyRevenue[item.month] = 0;
        }
        monthlyRevenue[item.month] += item.revenue;
    });
    
    return Object.entries(monthlyRevenue)
        .map(([month, revenue]) => ({ month, revenue }));
}

function analyzeCategoryPerformance(data) {
    const categoryStats = {};
    data.forEach(item => {
        if (!categoryStats[item.category]) {
            categoryStats[item.category] = {
                totalSales: 0,
                totalRevenue: 0,
                products: new Set()
            };
        }
        categoryStats[item.category].totalSales += item.sales;
        categoryStats[item.category].totalRevenue += item.revenue;
        categoryStats[item.category].products.add(item.product);
    });
    
    return Object.entries(categoryStats).map(([category, stats]) => ({
        category,
        totalSales: stats.totalSales,
        totalRevenue: stats.totalRevenue,
        productCount: stats.products.size
    }));
}

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
}); 