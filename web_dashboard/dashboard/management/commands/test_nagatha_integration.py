"""
Management command to test Nagatha integration and initialize system status.
"""
import asyncio
import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from dashboard.nagatha_adapter import NagathaAdapter
from dashboard.models import SystemStatus

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Nagatha integration and initialize system status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force refresh even if status exists',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing Nagatha integration...'))
        
        try:
            # Test Nagatha adapter
            adapter = NagathaAdapter()
            
            # Test system status
            self.stdout.write('Getting system status...')
            status_info = asyncio.run(adapter.get_system_status())
            
            self.stdout.write(self.style.SUCCESS('System status retrieved successfully'))
            self.stdout.write(f"MCP Servers: {status_info.get('mcp_servers_connected', 0)}")
            self.stdout.write(f"Tools Available: {status_info.get('total_tools_available', 0)}")
            self.stdout.write(f"System Health: {status_info.get('system_health', 'unknown')}")
            
            # Create or update system status
            if options['force'] or not SystemStatus.objects.exists():
                SystemStatus.objects.create(
                    mcp_servers_connected=status_info.get('mcp_servers_connected', 0),
                    total_tools_available=status_info.get('total_tools_available', 0),
                    active_sessions=status_info.get('active_sessions', 0),
                    system_health=status_info.get('system_health', 'unknown'),
                    cpu_usage=status_info.get('cpu_usage'),
                    memory_usage=status_info.get('memory_usage'),
                    disk_usage=status_info.get('disk_usage'),
                    additional_metrics=status_info.get('additional_metrics', {})
                )
                self.stdout.write(self.style.SUCCESS('System status created'))
            else:
                self.stdout.write('System status already exists (use --force to refresh)')
            
            # Test message sending (optional)
            self.stdout.write('Testing message sending...')
            try:
                # Test with a simple message that doesn't require database operations
                response = asyncio.run(adapter.send_message(None, "Hello, this is a test message"))
                self.stdout.write(self.style.SUCCESS(f'Message test successful: {response[:100]}...'))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'Message test failed: {e}'))
                # Try a simpler test without database operations
                self.stdout.write('Trying simple response test...')
                try:
                    from dashboard.tasks import get_simple_response
                    simple_response = get_simple_response("Hello")
                    self.stdout.write(self.style.SUCCESS(f'Simple response test successful: {simple_response[:100]}...'))
                except Exception as simple_error:
                    self.stdout.write(self.style.ERROR(f'Simple response test also failed: {simple_error}'))
            
            self.stdout.write(self.style.SUCCESS('Nagatha integration test completed successfully'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Nagatha integration test failed: {e}'))
            logger.error(f'Command failed: {e}', exc_info=True)
            return 1
        
        return 0 