"""
Resource Monitor Widget for Nagatha Assistant Dashboard.

This widget displays:
- System resource usage (CPU, memory, disk)
- Database metrics and statistics
- MCP server performance
- Event bus activity
- Token usage and costs (OpenAI API)
"""

import asyncio
import psutil
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from textual.app import ComposeResult
from textual.widgets import Static, ProgressBar, Collapsible, DataTable
from textual.containers import Vertical, Horizontal, Grid
from textual.reactive import reactive

from nagatha_assistant.core.event_bus import get_event_bus
from nagatha_assistant.utils.usage_tracker import load_usage
from nagatha_assistant.utils.logger import setup_logger_with_env_control

logger = setup_logger_with_env_control()


class ResourceMetrics:
    """Container for system resource metrics."""
    
    def __init__(self):
        # CPU metrics
        self.cpu_percent = 0.0
        self.cpu_count = 0
        self.cpu_freq_mhz = 0.0
        self.cpu_per_core = []
        
        # Memory metrics
        self.memory_percent = 0.0
        self.memory_used_mb = 0
        self.memory_total_mb = 0
        self.memory_available_mb = 0
        self.memory_free_mb = 0
        self.swap_percent = 0.0
        self.swap_used_mb = 0
        self.swap_total_mb = 0
        
        # Disk metrics
        self.disk_percent = 0.0
        self.disk_used_gb = 0
        self.disk_total_gb = 0
        self.disk_free_gb = 0
        
        # Network metrics
        self.network_bytes_sent_mb = 0
        self.network_bytes_recv_mb = 0
        self.network_connections = 0
        
        # System metrics
        self.process_count = 0
        self.uptime_seconds = 0
        self.boot_time = 0
        
        # Temperature (if available)
        self.cpu_temp_celsius = None
        
    @classmethod
    async def collect(cls) -> 'ResourceMetrics':
        """Collect current system metrics."""
        metrics = cls()
        
        try:
            # CPU metrics
            metrics.cpu_percent = psutil.cpu_percent(interval=1)
            metrics.cpu_count = psutil.cpu_count()
            cpu_freq = psutil.cpu_freq()
            if cpu_freq:
                metrics.cpu_freq_mhz = cpu_freq.current
            metrics.cpu_per_core = psutil.cpu_percent(interval=1, percpu=True)
            
            # Memory metrics
            memory = psutil.virtual_memory()
            metrics.memory_percent = memory.percent
            metrics.memory_used_mb = memory.used // (1024 * 1024)
            metrics.memory_total_mb = memory.total // (1024 * 1024)
            metrics.memory_available_mb = memory.available // (1024 * 1024)
            metrics.memory_free_mb = memory.free // (1024 * 1024)
            
            # Swap metrics
            swap = psutil.swap_memory()
            metrics.swap_percent = swap.percent
            metrics.swap_used_mb = swap.used // (1024 * 1024)
            metrics.swap_total_mb = swap.total // (1024 * 1024)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            metrics.disk_percent = (disk.used / disk.total) * 100
            metrics.disk_used_gb = disk.used // (1024 * 1024 * 1024)
            metrics.disk_total_gb = disk.total // (1024 * 1024 * 1024)
            metrics.disk_free_gb = disk.free // (1024 * 1024 * 1024)
            
            # Network metrics
            net_io = psutil.net_io_counters()
            metrics.network_bytes_sent_mb = net_io.bytes_sent // (1024 * 1024)
            metrics.network_bytes_recv_mb = net_io.bytes_recv // (1024 * 1024)
            metrics.network_connections = len(psutil.net_connections())
            
            # System metrics
            metrics.process_count = len(psutil.pids())
            metrics.boot_time = psutil.boot_time()
            metrics.uptime_seconds = int(datetime.now().timestamp() - metrics.boot_time)
            
            # Temperature (try to get CPU temperature)
            try:
                # Try to read temperature from common locations
                temp_paths = [
                    '/sys/class/thermal/thermal_zone0/temp',
                    '/sys/class/hwmon/hwmon0/temp1_input',
                    '/proc/acpi/thermal_zone/THM0/temperature'
                ]
                for temp_path in temp_paths:
                    if os.path.exists(temp_path):
                        with open(temp_path, 'r') as f:
                            temp_raw = f.read().strip()
                            # Most files return temperature in millidegrees
                            if temp_raw.isdigit():
                                temp_celsius = int(temp_raw) / 1000.0
                                metrics.cpu_temp_celsius = temp_celsius
                                break
            except Exception:
                # Temperature reading is optional
                pass
            
        except Exception as e:
            logger.warning(f"Error collecting system metrics: {e}")
            
        return metrics


class DatabaseMetrics:
    """Container for database metrics."""
    
    def __init__(self):
        self.total_sessions = 0
        self.total_messages = 0
        self.total_tasks = 0
        self.total_notes = 0
        self.db_size_mb = 0
        self.recent_activity_count = 0
        
    @classmethod
    async def collect(cls) -> 'DatabaseMetrics':
        """Collect database metrics."""
        metrics = cls()
        
        try:
            # For now, return empty metrics as we'd need database queries
            # In real implementation, would query the database for these stats
            pass
        except Exception as e:
            logger.warning(f"Error collecting database metrics: {e}")
            
        return metrics


class MCPMetrics:
    """Container for MCP server metrics."""
    
    def __init__(self):
        self.connected_servers = 0
        self.total_servers = 0
        self.available_tools = 0
        self.recent_tool_calls = 0
        self.average_response_time = 0.0
        self.failed_calls = 0
        
    @classmethod
    async def collect(cls) -> 'MCPMetrics':
        """Collect MCP metrics."""
        metrics = cls()
        
        try:
            # Get MCP status from agent
            from nagatha_assistant.core import agent
            mcp_status = await agent.get_mcp_status()
            
            summary = mcp_status.get('summary', {})
            metrics.connected_servers = summary.get('connected', 0)
            metrics.total_servers = summary.get('total_configured', 0)
            metrics.available_tools = summary.get('total_tools', 0)
            
        except Exception as e:
            logger.warning(f"Error collecting MCP metrics: {e}")
            
        return metrics


class TokenUsageMetrics:
    """Container for token usage and cost metrics."""
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        self.today_cost = 0.0
        self.requests_count = 0
        self.average_tokens_per_request = 0
        
    @classmethod
    async def collect(cls) -> 'TokenUsageMetrics':
        """Collect token usage metrics."""
        metrics = cls()
        
        try:
            usage_data = load_usage()
            
            # Calculate totals from the usage data
            total_input = 0
            total_output = 0
            total_cost = 0.0
            request_count = 0
            
            for model, data in usage_data.items():
                total_input += data.get('input_tokens', 0)
                total_output += data.get('output_tokens', 0)
                total_cost += data.get('cost', 0.0)
                request_count += data.get('requests', 0)
            
            metrics.total_input_tokens = total_input
            metrics.total_output_tokens = total_output
            metrics.total_cost = total_cost
            metrics.requests_count = request_count
            
            if metrics.requests_count > 0:
                total_tokens = metrics.total_input_tokens + metrics.total_output_tokens
                metrics.average_tokens_per_request = total_tokens / metrics.requests_count
            
            # For now, set today's cost to total cost (simplified)
            metrics.today_cost = total_cost
            
        except Exception as e:
            logger.warning(f"Error collecting token usage metrics: {e}")
            
        return metrics


class ResourceMonitor(Vertical):
    """
    Widget that displays system and application resource usage.
    """
    
    # Regular attributes for tracking values
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.refresh_interval = 5  # seconds
        self.metrics_history: List[ResourceMetrics] = []
        self.max_history = 60  # Keep 5 minutes of history
        self._update_timer = None
        
    def compose(self) -> ComposeResult:
        """Compose the resource monitor interface."""
        
        # System Resources Section
        with Collapsible(title="System Resources", collapsed=False, id="system_resources"):
            # CPU Usage
            with Vertical(classes="resource-item"):
                yield Static("💻 CPU Usage", classes="resource-label")
                yield Static("0% @ 0MHz", id="cpu_value", classes="resource-value")
                yield Static("", id="cpu_details", classes="resource-details")
            
            # Memory Usage  
            with Vertical(classes="resource-item"):
                yield Static("🧠 Memory Usage", classes="resource-label")
                yield Static("0% (0MB / 0MB)", id="memory_value", classes="resource-value")
                yield Static("", id="memory_details", classes="resource-details")
            
            # Disk Usage
            with Vertical(classes="resource-item"):
                yield Static("💾 Disk Usage", classes="resource-label")
                yield Static("0% (0GB / 0GB)", id="disk_value", classes="resource-value")
                yield Static("", id="disk_details", classes="resource-details")
            
            # Network Usage
            with Vertical(classes="resource-item"):
                yield Static("🌐 Network Usage", classes="resource-label")
                yield Static("", id="network_value", classes="resource-value")
                yield Static("", id="network_details", classes="resource-details")
            
            # System Info
            with Vertical(classes="resource-item"):
                yield Static("⚙️ System Info", classes="resource-label")
                yield Static("", id="system_value", classes="resource-value")
                yield Static("", id="system_details", classes="resource-details")
        
        # Application Metrics Section
        with Collapsible(title="Application Metrics", collapsed=False, id="app_metrics"):
            yield Static("Loading application metrics...", id="app_summary")
            
        # Database Metrics Section
        with Collapsible(title="Database Statistics", collapsed=True, id="db_metrics"):
            db_table = DataTable(id="db_table")
            db_table.add_columns("Metric", "Value")
            yield db_table
            
        # MCP Performance Section
        with Collapsible(title="MCP Performance", collapsed=True, id="mcp_metrics"):
            mcp_table = DataTable(id="mcp_table")
            mcp_table.add_columns("Metric", "Value", "Status")
            yield mcp_table
            
        # Token Usage Section
        with Collapsible(title="Token Usage & Costs", collapsed=True, id="token_metrics"):
            with Vertical(id="token_details"):
                yield Static("Loading token usage...", id="token_summary")
                token_table = DataTable(id="token_table")
                token_table.add_columns("Period", "Tokens", "Cost")
                yield token_table
    
    async def on_mount(self) -> None:
        """Initialize the resource monitor when mounted."""
        try:
            logger.info("ResourceMonitor: Starting initialization...")
            
            # Debug: Check what widgets were created
            logger.info("ResourceMonitor: Checking created widgets...")
            cpu_value = self.query_one("#cpu_value", Static)
            memory_value = self.query_one("#memory_value", Static)
            disk_value = self.query_one("#disk_value", Static)
            
            logger.info(f"ResourceMonitor: Value widgets found - CPU Value: {cpu_value is not None}, Memory Value: {memory_value is not None}, Disk Value: {disk_value is not None}")
            
            # Start periodic updates
            self._update_timer = self.set_interval(self.refresh_interval, self._update_all_metrics)
            logger.info(f"ResourceMonitor: Set update interval to {self.refresh_interval}s")
            
            # Initial load
            logger.info("ResourceMonitor: Performing initial metrics update...")
            await self._update_all_metrics()
            logger.info("ResourceMonitor: Initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Error initializing resource monitor: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _update_all_metrics(self) -> None:
        """Update all metrics displays."""
        try:
            logger.debug("ResourceMonitor: Starting metrics collection...")
            
            # Collect all metrics concurrently
            system_metrics, db_metrics, mcp_metrics, token_metrics = await asyncio.gather(
                ResourceMetrics.collect(),
                DatabaseMetrics.collect(),
                MCPMetrics.collect(),
                TokenUsageMetrics.collect(),
                return_exceptions=True
            )
            
            logger.debug(f"ResourceMonitor: Collected metrics - System: {type(system_metrics)}, DB: {type(db_metrics)}, MCP: {type(mcp_metrics)}, Token: {type(token_metrics)}")
            
            # Update displays
            if isinstance(system_metrics, ResourceMetrics):
                logger.debug(f"ResourceMonitor: Updating system resources - CPU: {system_metrics.cpu_percent}%, Memory: {system_metrics.memory_percent}%, Disk: {system_metrics.disk_percent}%")
                await self._update_system_resources(system_metrics)
            else:
                logger.warning(f"ResourceMonitor: System metrics collection failed: {system_metrics}")
                
            if isinstance(db_metrics, DatabaseMetrics):
                await self._update_database_metrics(db_metrics)
                
            if isinstance(mcp_metrics, MCPMetrics):
                await self._update_mcp_metrics(mcp_metrics)
                
            if isinstance(token_metrics, TokenUsageMetrics):
                await self._update_token_metrics(token_metrics)
            
            # Update application summary
            await self._update_application_summary()
            
        except Exception as e:
            logger.error(f"Error updating metrics: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _update_system_resources(self, metrics: ResourceMetrics) -> None:
        """Update system resource displays."""
        try:
            logger.debug(f"ResourceMonitor: Updating system resources display - CPU: {metrics.cpu_percent}%, Memory: {metrics.memory_percent}%, Disk: {metrics.disk_percent}%")
            
            # Add to history
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history:
                self.metrics_history = self.metrics_history[-self.max_history:]
            
            # Update reactive attributes
            self.cpu_usage = metrics.cpu_percent
            self.memory_usage = metrics.memory_percent
            self.disk_usage = metrics.disk_percent
            
            # Progress bars removed - focusing only on values
            
            # Update value labels with both percentage and actual values
            try:
                cpu_value = self.query_one("#cpu_value", Static)
                if cpu_value:
                    # Show percentage and frequency
                    freq_info = f" @ {metrics.cpu_freq_mhz:.0f}MHz" if metrics.cpu_freq_mhz > 0 else ""
                    cpu_value.update(f"{metrics.cpu_percent:.1f}%{freq_info}")
                    logger.debug(f"ResourceMonitor: Updated CPU value label to {metrics.cpu_percent:.1f}%{freq_info}")
                else:
                    logger.warning("ResourceMonitor: CPU value label not found")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating CPU value label: {e}")
            
            try:
                memory_value = self.query_one("#memory_value", Static)
                if memory_value:
                    # Show percentage and actual values
                    memory_value.update(f"{metrics.memory_percent:.1f}% ({metrics.memory_used_mb}MB / {metrics.memory_total_mb}MB)")
                    logger.debug(f"ResourceMonitor: Updated memory value label to {metrics.memory_percent:.1f}% ({metrics.memory_used_mb}MB / {metrics.memory_total_mb}MB)")
                else:
                    logger.warning("ResourceMonitor: Memory value label not found")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating memory value label: {e}")
            
            try:
                disk_value = self.query_one("#disk_value", Static)
                if disk_value:
                    # Show percentage and actual values
                    disk_value.update(f"{metrics.disk_percent:.1f}% ({metrics.disk_used_gb}GB / {metrics.disk_total_gb}GB)")
                    logger.debug(f"ResourceMonitor: Updated disk value label to {metrics.disk_percent:.1f}% ({metrics.disk_used_gb}GB / {metrics.disk_total_gb}GB)")
                else:
                    logger.warning("ResourceMonitor: Disk value label not found")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating disk value label: {e}")
            
            # Update detailed information
            await self._update_detailed_resources(metrics)
            
            # Check for resource alerts
            self.check_resource_alerts(metrics)
            
        except Exception as e:
            logger.error(f"Error updating system resources: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _update_detailed_resources(self, metrics: ResourceMetrics) -> None:
        """Update detailed resource information displays."""
        try:
            # CPU Details
            try:
                cpu_details = self.query_one("#cpu_details", Static)
                if cpu_details:
                    temp_info = f"Temp: {metrics.cpu_temp_celsius:.1f}°C" if metrics.cpu_temp_celsius else ""
                    core_info = f"{metrics.cpu_count} cores"
                    
                    details = [core_info]
                    if temp_info:
                        details.append(temp_info)
                    
                    cpu_details.update(" | ".join(details))
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating CPU details: {e}")
            
            # Memory Details
            try:
                memory_details = self.query_one("#memory_details", Static)
                if memory_details:
                    available_gb = metrics.memory_available_mb / 1024
                    free_gb = metrics.memory_free_mb / 1024
                    swap_info = f"Swap: {metrics.swap_used_mb}MB/{metrics.swap_total_mb}MB" if metrics.swap_total_mb > 0 else ""
                    
                    details = [f"Available: {available_gb:.1f}GB", f"Free: {free_gb:.1f}GB"]
                    if swap_info:
                        details.append(swap_info)
                    
                    memory_details.update(" | ".join(details))
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating memory details: {e}")
            
            # Disk Details
            try:
                disk_details = self.query_one("#disk_details", Static)
                if disk_details:
                    free_gb = metrics.disk_free_gb
                    disk_details.update(f"Free: {free_gb:.1f}GB")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating disk details: {e}")
            
            # Network Details
            try:
                network_value = self.query_one("#network_value", Static)
                network_details = self.query_one("#network_details", Static)
                
                if network_value and network_details:
                    sent_gb = metrics.network_bytes_sent_mb / 1024
                    recv_gb = metrics.network_bytes_recv_mb / 1024
                    
                    network_value.update(f"↑ {sent_gb:.1f}GB | ↓ {recv_gb:.1f}GB")
                    network_details.update(f"Connections: {metrics.network_connections}")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating network details: {e}")
            
            # System Details
            try:
                system_value = self.query_one("#system_value", Static)
                system_details = self.query_one("#system_details", Static)
                
                if system_value and system_details:
                    uptime_hours = metrics.uptime_seconds / 3600
                    uptime_days = uptime_hours / 24
                    
                    if uptime_days >= 1:
                        uptime_str = f"{uptime_days:.1f} days"
                    else:
                        uptime_str = f"{uptime_hours:.1f} hours"
                    
                    system_value.update(f"Uptime: {uptime_str}")
                    system_details.update(f"Processes: {metrics.process_count} | Boot: {datetime.fromtimestamp(metrics.boot_time).strftime('%Y-%m-%d %H:%M')}")
            except Exception as e:
                logger.error(f"ResourceMonitor: Error updating system details: {e}")
                
        except Exception as e:
            logger.error(f"Error updating detailed resources: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def _update_application_summary(self) -> None:
        """Update application metrics summary."""
        try:
            app_summary = self.query_one("#app_summary", Static)
            
            # Get event bus activity
            event_bus = get_event_bus()
            recent_events = event_bus.get_event_history(limit=10)
            
            # Calculate uptime
            uptime_hours = 0
            if self.metrics_history:
                uptime_hours = self.metrics_history[-1].uptime_seconds / 3600
            
            summary_text = (
                f"🚀 Application Status: Running\n"
                f"⏱️ System Uptime: {uptime_hours:.1f} hours\n"
                f"📊 Recent Events: {len(recent_events)}\n"
                f"🔄 Update Interval: {self.refresh_interval}s"
            )
            
            app_summary.update(summary_text)
            
        except Exception as e:
            logger.error(f"Error updating application summary: {e}")
    
    async def _update_database_metrics(self, metrics: DatabaseMetrics) -> None:
        """Update database metrics display."""
        try:
            db_table = self.query_one("#db_table", DataTable)
            db_table.clear()
            
            # Add database metrics
            db_table.add_row("Sessions", str(metrics.total_sessions))
            db_table.add_row("Messages", str(metrics.total_messages))
            db_table.add_row("Tasks", str(metrics.total_tasks))
            db_table.add_row("Notes", str(metrics.total_notes))
            db_table.add_row("DB Size", f"{metrics.db_size_mb} MB")
            db_table.add_row("Recent Activity", str(metrics.recent_activity_count))
            
        except Exception as e:
            logger.error(f"Error updating database metrics: {e}")
    
    async def _update_mcp_metrics(self, metrics: MCPMetrics) -> None:
        """Update MCP metrics display."""
        try:
            mcp_table = self.query_one("#mcp_table", DataTable)
            mcp_table.clear()
            
            # Server status
            server_status = "🟢 Good" if metrics.connected_servers == metrics.total_servers else "⚠️ Partial"
            if metrics.connected_servers == 0:
                server_status = "🔴 Down"
                
            mcp_table.add_row("Connected Servers", f"{metrics.connected_servers}/{metrics.total_servers}", server_status)
            mcp_table.add_row("Available Tools", str(metrics.available_tools), "🟢 Ready")
            mcp_table.add_row("Recent Tool Calls", str(metrics.recent_tool_calls), "📊 Active")
            
            if metrics.average_response_time > 0:
                response_status = "🟢 Fast" if metrics.average_response_time < 1.0 else "⚠️ Slow"
                mcp_table.add_row("Avg Response Time", f"{metrics.average_response_time:.2f}s", response_status)
            
            if metrics.failed_calls > 0:
                mcp_table.add_row("Failed Calls", str(metrics.failed_calls), "🔴 Error")
            
        except Exception as e:
            logger.error(f"Error updating MCP metrics: {e}")
    
    async def _update_token_metrics(self, metrics: TokenUsageMetrics) -> None:
        """Update token usage and cost metrics."""
        try:
            token_summary = self.query_one("#token_summary", Static)
            token_table = self.query_one("#token_table", DataTable)
            
            # Update summary
            summary_text = (
                f"💰 Total Cost: ${metrics.total_cost:.4f}\n"
                f"📈 Today's Cost: ${metrics.today_cost:.4f}\n"
                f"🔢 Total Tokens: {metrics.total_input_tokens + metrics.total_output_tokens:,}\n"
                f"📊 Avg Tokens/Request: {metrics.average_tokens_per_request:.0f}"
            )
            token_summary.update(summary_text)
            
            # Update table
            token_table.clear()
            token_table.add_row(
                "Total", 
                f"{metrics.total_input_tokens + metrics.total_output_tokens:,}",
                f"${metrics.total_cost:.4f}"
            )
            token_table.add_row(
                "Today",
                f"{metrics.total_input_tokens:,} in / {metrics.total_output_tokens:,} out",
                f"${metrics.today_cost:.4f}"
            )
            token_table.add_row(
                "Requests",
                str(metrics.requests_count),
                f"${(metrics.total_cost/metrics.requests_count):.4f}/req" if metrics.requests_count > 0 else "$0.00/req"
            )
            
        except Exception as e:
            logger.error(f"Error updating token metrics: {e}")
    
    def get_resource_trend(self, resource_type: str, periods: int = 10) -> List[float]:
        """Get trend data for a specific resource type."""
        if len(self.metrics_history) < periods:
            return []
            
        recent_metrics = self.metrics_history[-periods:]
        
        if resource_type == "cpu":
            return [m.cpu_percent for m in recent_metrics]
        elif resource_type == "memory":
            return [m.memory_percent for m in recent_metrics]
        elif resource_type == "disk":
            return [m.disk_percent for m in recent_metrics]
        else:
            return []
    
    def set_refresh_interval(self, interval_seconds: int) -> None:
        """Change the refresh interval for resource monitoring."""
        if interval_seconds < 1:
            interval_seconds = 1
        elif interval_seconds > 60:
            interval_seconds = 60
            
        self.refresh_interval = interval_seconds
        
        # Restart the timer with new interval
        if self._update_timer:
            self._update_timer.stop()
        
        self._update_timer = self.set_interval(self.refresh_interval, self._update_all_metrics)
        logger.info(f"ResourceMonitor: Changed update interval to {self.refresh_interval}s")
    
    def get_current_metrics(self) -> Optional[ResourceMetrics]:
        """Get the most recent resource metrics."""
        if self.metrics_history:
            return self.metrics_history[-1]
        return None
    
    def check_resource_alerts(self, metrics: ResourceMetrics) -> None:
        """Check for resource usage alerts."""
        if metrics.cpu_percent > 80:
            logger.warning(f"High CPU usage detected: {metrics.cpu_percent}%")
        
        if metrics.memory_percent > 85:
            logger.warning(f"High memory usage detected: {metrics.memory_percent}%")
        
        if metrics.disk_percent > 90:
            logger.warning(f"High disk usage detected: {metrics.disk_percent}%")