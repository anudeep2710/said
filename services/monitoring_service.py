#!/usr/bin/env python3
"""
Monitoring and logging service with Google Cloud integration
"""

import os
import time
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

try:
    from google.cloud import logging as cloud_logging
    from google.cloud import monitoring_v3
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False
    cloud_logging = None
    monitoring_v3 = None

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class MetricType(Enum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"

@dataclass
class MetricData:
    name: str
    value: float
    labels: Dict[str, str]
    timestamp: datetime
    metric_type: MetricType

class MonitoringService:
    """Comprehensive monitoring service"""
    
    def __init__(self):
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "said-eb2f5")
        self.cloud_logging_client = None
        self.monitoring_client = None
        self.prometheus_metrics = {}
        
        # Application metrics
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        
        # Initialize services
        self._initialize_cloud_logging()
        self._initialize_cloud_monitoring()
        self._initialize_prometheus()
    
    def _initialize_cloud_logging(self):
        """Initialize Google Cloud Logging"""
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.cloud_logging_client = cloud_logging.Client(project=self.project_id)
                self.cloud_logging_client.setup_logging()
                logger.info("Google Cloud Logging initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Cloud Logging: {str(e)}")
    
    def _initialize_cloud_monitoring(self):
        """Initialize Google Cloud Monitoring"""
        if GOOGLE_CLOUD_AVAILABLE:
            try:
                self.monitoring_client = monitoring_v3.MetricServiceClient()
                logger.info("Google Cloud Monitoring initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Cloud Monitoring: {str(e)}")
    
    def _initialize_prometheus(self):
        """Initialize Prometheus metrics"""
        if PROMETHEUS_AVAILABLE:
            try:
                # Define application metrics
                self.prometheus_metrics = {
                    'requests_total': Counter(
                        'talktoyourdocument_requests_total',
                        'Total number of requests',
                        ['method', 'endpoint', 'status']
                    ),
                    'request_duration': Histogram(
                        'talktoyourdocument_request_duration_seconds',
                        'Request duration in seconds',
                        ['method', 'endpoint']
                    ),
                    'documents_total': Gauge(
                        'talktoyourdocument_documents_total',
                        'Total number of documents',
                        ['user_type']
                    ),
                    'ai_queries_total': Counter(
                        'talktoyourdocument_ai_queries_total',
                        'Total number of AI queries',
                        ['query_type', 'status']
                    ),
                    'cache_hits_total': Counter(
                        'talktoyourdocument_cache_hits_total',
                        'Total number of cache hits',
                        ['cache_type']
                    ),
                    'errors_total': Counter(
                        'talktoyourdocument_errors_total',
                        'Total number of errors',
                        ['error_type', 'endpoint']
                    ),
                    'active_users': Gauge(
                        'talktoyourdocument_active_users',
                        'Number of active users',
                        ['time_window']
                    )
                }
                
                # Start Prometheus HTTP server
                prometheus_port = int(os.getenv("PROMETHEUS_PORT", "9090"))
                start_http_server(prometheus_port)
                logger.info(f"Prometheus metrics server started on port {prometheus_port}")
                
            except Exception as e:
                logger.warning(f"Failed to initialize Prometheus: {str(e)}")
    
    def log_request(self, method: str, endpoint: str, status_code: int, duration: float, user_id: Optional[str] = None):
        """Log request metrics"""
        self.request_count += 1
        
        # Prometheus metrics
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['requests_total'].labels(
                method=method,
                endpoint=endpoint,
                status=str(status_code)
            ).inc()
            
            self.prometheus_metrics['request_duration'].labels(
                method=method,
                endpoint=endpoint
            ).observe(duration)
        
        # Log to Cloud Logging
        if status_code >= 400:
            self.error_count += 1
            logger.warning(f"Request error: {method} {endpoint} - {status_code} ({duration:.3f}s)")
        else:
            logger.info(f"Request: {method} {endpoint} - {status_code} ({duration:.3f}s)")
    
    def log_ai_query(self, query_type: str, success: bool, duration: float, user_id: Optional[str] = None):
        """Log AI query metrics"""
        status = "success" if success else "error"
        
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['ai_queries_total'].labels(
                query_type=query_type,
                status=status
            ).inc()
        
        logger.info(f"AI Query: {query_type} - {status} ({duration:.3f}s)")
    
    def log_cache_hit(self, cache_type: str, hit: bool):
        """Log cache hit/miss"""
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['cache_hits_total'].labels(
                cache_type=cache_type
            ).inc()
        
        logger.debug(f"Cache {'hit' if hit else 'miss'}: {cache_type}")
    
    def log_error(self, error_type: str, endpoint: str, error_message: str, user_id: Optional[str] = None):
        """Log application errors"""
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['errors_total'].labels(
                error_type=error_type,
                endpoint=endpoint
            ).inc()
        
        logger.error(f"Application error: {error_type} at {endpoint} - {error_message}")
    
    def update_document_count(self, count: int, user_type: str = "all"):
        """Update document count metric"""
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['documents_total'].labels(
                user_type=user_type
            ).set(count)
    
    def update_active_users(self, count: int, time_window: str = "1h"):
        """Update active users metric"""
        if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
            self.prometheus_metrics['active_users'].labels(
                time_window=time_window
            ).set(count)
    
    async def send_custom_metric(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Send custom metric to Google Cloud Monitoring"""
        if not self.monitoring_client:
            return
        
        try:
            project_name = f"projects/{self.project_id}"
            
            # Create time series data
            series = monitoring_v3.TimeSeries()
            series.metric.type = f"custom.googleapis.com/talktoyourdocument/{metric_name}"
            
            # Add labels
            if labels:
                for key, val in labels.items():
                    series.metric.labels[key] = val
            
            # Set resource
            series.resource.type = "global"
            
            # Create data point
            point = series.points.add()
            point.value.double_value = value
            point.interval.end_time.seconds = int(time.time())
            
            # Send to Cloud Monitoring
            self.monitoring_client.create_time_series(
                name=project_name,
                time_series=[series]
            )
            
        except Exception as e:
            logger.error(f"Failed to send custom metric: {str(e)}")
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics"""
        import psutil
        
        # Basic system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Application metrics
        uptime = time.time() - self.start_time
        
        # Cache metrics
        cache_type = cache_service.get_cache_type() if cache_service else "unknown"
        
        metrics = {
            "system": {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_mb": memory.used // (1024 * 1024),
                "memory_total_mb": memory.total // (1024 * 1024),
                "disk_percent": disk.percent,
                "disk_used_gb": disk.used // (1024 * 1024 * 1024),
                "disk_total_gb": disk.total // (1024 * 1024 * 1024)
            },
            "application": {
                "uptime_seconds": uptime,
                "total_requests": self.request_count,
                "total_errors": self.error_count,
                "error_rate": self.error_count / max(self.request_count, 1),
                "cache_type": cache_type
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return metrics
    
    async def health_check(self) -> Dict[str, Any]:
        """Comprehensive health check"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {},
            "metrics": {}
        }
        
        try:
            # Check Cloud Logging
            health_status["services"]["cloud_logging"] = "available" if self.cloud_logging_client else "unavailable"
            
            # Check Cloud Monitoring
            health_status["services"]["cloud_monitoring"] = "available" if self.monitoring_client else "unavailable"
            
            # Check Prometheus
            health_status["services"]["prometheus"] = "available" if PROMETHEUS_AVAILABLE else "unavailable"
            
            # Get system metrics
            health_status["metrics"] = await self.get_system_metrics()
            
            # Check if any critical issues
            system_metrics = health_status["metrics"]["system"]
            if system_metrics["cpu_percent"] > 90:
                health_status["status"] = "warning"
            if system_metrics["memory_percent"] > 90:
                health_status["status"] = "warning"
            if system_metrics["disk_percent"] > 90:
                health_status["status"] = "critical"
            
        except Exception as e:
            health_status["status"] = "error"
            health_status["error"] = str(e)
            logger.error(f"Health check failed: {str(e)}")
        
        return health_status
    
    async def start_background_tasks(self):
        """Start background monitoring tasks"""
        asyncio.create_task(self._periodic_metrics_collection())
        asyncio.create_task(self._cleanup_old_logs())
        logger.info("Background monitoring tasks started")
    
    async def _periodic_metrics_collection(self):
        """Collect and send metrics periodically"""
        while True:
            try:
                # Collect system metrics
                metrics = await self.get_system_metrics()
                
                # Send to Cloud Monitoring
                await self.send_custom_metric("cpu_usage", metrics["system"]["cpu_percent"])
                await self.send_custom_metric("memory_usage", metrics["system"]["memory_percent"])
                await self.send_custom_metric("request_count", metrics["application"]["total_requests"])
                
                # Update Prometheus gauges
                if PROMETHEUS_AVAILABLE and self.prometheus_metrics:
                    # Update system metrics in Prometheus would go here
                    pass
                
                await asyncio.sleep(60)  # Collect every minute
                
            except Exception as e:
                logger.error(f"Periodic metrics collection failed: {str(e)}")
                await asyncio.sleep(60)
    
    async def _cleanup_old_logs(self):
        """Clean up old log entries"""
        while True:
            try:
                # This would implement log rotation and cleanup
                # For now, just sleep
                await asyncio.sleep(3600)  # Check every hour
                
            except Exception as e:
                logger.error(f"Log cleanup failed: {str(e)}")
                await asyncio.sleep(3600)

# Global monitoring service instance
monitoring_service = MonitoringService()

# Middleware for automatic request monitoring
class MonitoringMiddleware:
    """Middleware to automatically monitor requests"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            start_time = time.time()
            
            # Extract request info
            method = scope["method"]
            path = scope["path"]
            
            # Process request
            await self.app(scope, receive, send)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log metrics (status code would need to be extracted from response)
            monitoring_service.log_request(method, path, 200, duration)  # Simplified
        else:
            await self.app(scope, receive, send)
