"""
HTTP API Server for Bridge

Provides a simple HTTP API to query bridge status and client count.
"""

import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
from typing import Optional

from client_table import ActiveClientTable
from config import BRIDGE_API_PORT


logger = logging.getLogger(__name__)


class BridgeAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for bridge API."""
    
    client_table: Optional[ActiveClientTable] = None
    
    def log_message(self, format, *args):
        """Override to use our logger instead of stderr."""
        logger.debug(f"{self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Handle GET requests."""
        if self.path == '/api/clients':
            self.handle_clients_request()
        elif self.path == '/api/status':
            self.handle_status_request()
        else:
            self.send_error(404, "Not Found")
    
    def handle_clients_request(self):
        """Return client count and list."""
        try:
            if self.client_table is None:
                self.send_error(500, "Client table not initialized")
                return
            
            count = self.client_table.get_client_count()
            clients = self.client_table.get_active_clients()
            
            response = {
                'count': count,
                'clients': clients
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling clients request: {e}")
            self.send_error(500, str(e))
    
    def handle_status_request(self):
        """Return bridge status."""
        try:
            response = {
                'status': 'running',
                'service': 'bridge'
            }
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error handling status request: {e}")
            self.send_error(500, str(e))


class BridgeAPIServer:
    """Simple HTTP API server for bridge status queries."""
    
    def __init__(self, client_table: ActiveClientTable, port: int = BRIDGE_API_PORT):
        """
        Initialize the API server.
        
        Args:
            client_table: ActiveClientTable instance
            port: Port to listen on (default: 8080)
        """
        self.client_table = client_table
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        
        # Set class variable for handler
        BridgeAPIHandler.client_table = client_table
        
        logger.info(f"Bridge API server initialized on port {port}")
    
    def start(self):
        """Start the API server in a separate thread."""
        self._running = True
        
        def server_loop():
            try:
                self._server = HTTPServer(('0.0.0.0', self.port), BridgeAPIHandler)
                logger.info(f"Bridge API server listening on 0.0.0.0:{self.port}")
                
                while self._running:
                    self._server.handle_request()
                    
            except Exception as e:
                logger.error(f"API server error: {e}")
            finally:
                logger.info("API server stopped")
        
        self._thread = threading.Thread(target=server_loop, daemon=True)
        self._thread.start()
    
    def stop(self):
        """Stop the API server."""
        logger.info("Stopping API server...")
        self._running = False
        
        if self._server:
            self._server.shutdown()
            self._server = None
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        
        logger.info("API server stopped")
