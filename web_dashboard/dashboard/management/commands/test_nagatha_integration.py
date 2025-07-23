"""
Django management command to test Nagatha core integration with Celery.

Usage:
    python manage.py test_nagatha_integration
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.nagatha_celery_integration import (
    process_message_with_nagatha,
    check_mcp_servers_health,
    cleanup_memory_and_maintenance,
    track_usage_metrics,
    process_scheduled_tasks,
    reload_mcp_configuration
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test Nagatha core integration with Celery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=['message', 'mcp', 'memory', 'usage', 'scheduled', 'reload', 'all'],
            default='all',
            help='Which task to test (default: all)'
        )
        parser.add_argument(
            '--message',
            type=str,
            default='Hello from management command!',
            help='Message to send for message processing test'
        )

    def handle(self, *args, **options):
        task_type = options['task']
        message = options['message']
        
        self.stdout.write(
            self.style.SUCCESS(f'Starting Nagatha integration test for task: {task_type}')
        )
        
        try:
            if task_type in ['message', 'all']:
                self.test_message_processing(message)
            
            if task_type in ['mcp', 'all']:
                self.test_mcp_health_check()
            
            if task_type in ['memory', 'all']:
                self.test_memory_cleanup()
            
            if task_type in ['usage', 'all']:
                self.test_usage_tracking()
            
            if task_type in ['scheduled', 'all']:
                self.test_scheduled_tasks()
            
            if task_type in ['reload', 'all']:
                self.test_mcp_reload()
            
            self.stdout.write(
                self.style.SUCCESS('All tests completed successfully!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Test failed: {e}')
            )
            logger.error(f"Integration test failed: {e}")
    
    def test_message_processing(self, message):
        """Test message processing with Nagatha core."""
        self.stdout.write('Testing message processing...')
        
        # Start the task
        result = process_message_with_nagatha.delay(None, message)
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'Message processing successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Message processing failed: {task_result}')
            )
    
    def test_mcp_health_check(self):
        """Test MCP server health check."""
        self.stdout.write('Testing MCP health check...')
        
        # Start the task
        result = check_mcp_servers_health.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'MCP health check successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'MCP health check failed: {task_result}')
            )
    
    def test_memory_cleanup(self):
        """Test memory cleanup and maintenance."""
        self.stdout.write('Testing memory cleanup...')
        
        # Start the task
        result = cleanup_memory_and_maintenance.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'Memory cleanup successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Memory cleanup failed: {task_result}')
            )
    
    def test_usage_tracking(self):
        """Test usage metrics tracking."""
        self.stdout.write('Testing usage tracking...')
        
        # Start the task
        result = track_usage_metrics.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'Usage tracking successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Usage tracking failed: {task_result}')
            )
    
    def test_scheduled_tasks(self):
        """Test scheduled tasks processing."""
        self.stdout.write('Testing scheduled tasks...')
        
        # Start the task
        result = process_scheduled_tasks.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'Scheduled tasks successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'Scheduled tasks failed: {task_result}')
            )
    
    def test_mcp_reload(self):
        """Test MCP configuration reload."""
        self.stdout.write('Testing MCP reload...')
        
        # Start the task
        result = reload_mcp_configuration.delay()
        
        # Wait for result
        task_result = result.get(timeout=60)
        
        if task_result.get('success'):
            self.stdout.write(
                self.style.SUCCESS(f'MCP reload successful: {task_result}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'MCP reload failed: {task_result}')
            ) 