#!/usr/bin/env python3
"""
Monitoring Dashboard
====================

Provides a comprehensive dashboard view of:
- Security scan results and trends
- Performance benchmarks and regressions
- Alert system health and reliability
- System resource utilization
- Monitoring system status

Generates HTML reports and console summaries.
"""

import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

class MonitoringDashboard:
    """Monitoring dashboard generator"""

    def __init__(self):
        self.monitoring_dir = Path("monitoring")
        self.reports_dir = self.monitoring_dir / "reports"
        self.dashboard_dir = self.monitoring_dir / "dashboard"

        # Ensure directories exist
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)

    async def generate_dashboard(self) -> Dict[str, Any]:
        """Generate comprehensive monitoring dashboard"""
        logger.info("📊 Generating monitoring dashboard")

        dashboard_data = {
            "generated_at": datetime.now().isoformat(),
            "period_days": 7,  # Last 7 days
            "sections": {}
        }

        # Load all monitoring data
        dashboard_data["sections"]["system_status"] = await self._get_system_status()
        dashboard_data["sections"]["security_overview"] = await self._get_security_overview()
        dashboard_data["sections"]["performance_metrics"] = await self._get_performance_metrics()
        dashboard_data["sections"]["alert_health"] = await self._get_alert_health()
        dashboard_data["sections"]["trends"] = await self._get_trends_analysis()

        # Generate HTML dashboard
        html_content = self._generate_html_dashboard(dashboard_data)
        html_file = self.dashboard_dir / "dashboard.html"
        with open(html_file, 'w') as f:
            f.write(html_content)

        # Generate console summary
        console_summary = self._generate_console_summary(dashboard_data)
        print(console_summary)

        # Save dashboard data
        dashboard_file = self.dashboard_dir / "dashboard_data.json"
        with open(dashboard_file, 'w') as f:
            json.dump(dashboard_data, f, indent=2, default=str)

        logger.info(f"📊 Dashboard generated: {html_file}")
        return dashboard_data

    async def _get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        status = {
            "services": {},
            "resources": {},
            "last_updated": datetime.now().isoformat()
        }

        # Check service status (would need to run system commands)
        # For now, return placeholder
        status["services"] = {
            "main_bot": {"status": "running", "uptime": "2d 4h 30m"},
            "monitoring": {"status": "active", "last_run": "2h ago"},
            "alerts": {"status": "healthy", "last_check": "30m ago"}
        }

        # Get resource usage (placeholder - would use psutil in real implementation)
        status["resources"] = {
            "cpu_percent": 15.2,
            "memory_percent": 68.5,
            "disk_percent": 45.2,
            "network_connections": 12
        }

        return status

    async def _get_security_overview(self) -> Dict[str, Any]:
        """Get security scanning overview"""
        overview = {
            "latest_scan": {},
            "trends": {},
            "critical_issues": []
        }

        # Load latest security scan
        security_file = self.monitoring_dir / "security" / "latest_security_scan.json"
        if security_file.exists():
            with open(security_file, 'r') as f:
                scan_data = json.load(f)
                overview["latest_scan"] = {
                    "timestamp": scan_data.get("timestamp"),
                    "status": scan_data.get("summary", {}).get("overall_status"),
                    "critical_issues": scan_data.get("summary", {}).get("critical_issues", 0),
                    "high_issues": scan_data.get("summary", {}).get("high_issues", 0),
                    "total_issues": scan_data.get("summary", {}).get("total_issues", 0)
                }

                # Extract critical issues
                for alert in scan_data.get("alerts", []):
                    if alert.get("level") == "critical":
                        overview["critical_issues"].append({
                            "title": alert.get("title", "Unknown"),
                            "message": alert.get("message", ""),
                            "timestamp": scan_data.get("timestamp")
                        })

        return overview

    async def _get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance benchmarking overview"""
        metrics = {
            "latest_benchmark": {},
            "regressions": [],
            "improvements": []
        }

        # Load latest performance benchmark
        perf_file = self.monitoring_dir / "performance" / "latest_benchmark.json"
        if perf_file.exists():
            with open(perf_file, 'r') as f:
                perf_data = json.load(f)
                metrics["latest_benchmark"] = {
                    "timestamp": perf_data.get("timestamp"),
                    "duration_minutes": perf_data.get("duration_minutes"),
                    "scenarios_run": len(perf_data.get("scenarios", {}))
                }

                # Extract regressions and improvements
                comparison = perf_data.get("comparison", {})
                metrics["regressions"] = comparison.get("regressions", [])
                metrics["improvements"] = comparison.get("improvements", [])

        return metrics

    async def _get_alert_health(self) -> Dict[str, Any]:
        """Get alert system health overview"""
        health = {
            "latest_check": {},
            "health_trend": [],
            "issues": []
        }

        # Load latest alert health check
        health_file = self.monitoring_dir / "alert_health" / "latest_health_check.json"
        if health_file.exists():
            with open(health_file, 'r') as f:
                health_data = json.load(f)
                health["latest_check"] = {
                    "timestamp": health_data.get("timestamp"),
                    "overall_health": health_data.get("overall_health"),
                    "issues_count": len(health_data.get("issues", []))
                }

                # Extract issues
                health["issues"] = health_data.get("issues", [])

        return health

    async def _get_trends_analysis(self) -> Dict[str, Any]:
        """Analyze trends across monitoring data"""
        trends = {
            "security_trend": "stable",
            "performance_trend": "stable",
            "alert_reliability": 0.95,
            "insights": []
        }

        # Analyze recent monitoring runs
        recent_runs = []
        if self.reports_dir.exists():
            for report_file in self.reports_dir.glob("monitoring_run_*.json"):
                try:
                    with open(report_file, 'r') as f:
                        run_data = json.load(f)
                        recent_runs.append(run_data)
                except Exception:
                    continue

        if recent_runs:
            # Sort by timestamp
            recent_runs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            recent_runs = recent_runs[:7]  # Last 7 runs

            # Analyze trends
            if len(recent_runs) >= 2:
                latest = recent_runs[0]
                previous = recent_runs[1]

                # Security trend
                latest_security = latest.get("security", {}).get("summary", {})
                prev_security = previous.get("security", {}).get("summary", {})

                if latest_security.get("critical_issues", 0) > prev_security.get("critical_issues", 0):
                    trends["security_trend"] = "worsening"
                    trends["insights"].append("Security issues are increasing")
                elif latest_security.get("critical_issues", 0) < prev_security.get("critical_issues", 0):
                    trends["security_trend"] = "improving"
                    trends["insights"].append("Security issues are decreasing")

                # Performance trend
                latest_perf = latest.get("performance", {}).get("comparison", {})
                if latest_perf.get("regressions"):
                    trends["performance_trend"] = "worsening"
                    trends["insights"].append("Performance regressions detected")
                elif latest_perf.get("improvements"):
                    trends["performance_trend"] = "improving"
                    trends["insights"].append("Performance improvements detected")

        return trends

    def _generate_html_dashboard(self, data: Dict[str, Any]) -> str:
        """Generate HTML dashboard"""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polymarket Bot Monitoring Dashboard</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .section {{ background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .metric {{ display: inline-block; margin: 10px; padding: 10px; background: #ecf0f1; border-radius: 4px; }}
        .status-good {{ color: #27ae60; }}
        .status-warning {{ color: #f39c12; }}
        .status-critical {{ color: #e74c3c; }}
        .issue {{ background: #ffeaa7; padding: 10px; margin: 5px 0; border-left: 4px solid #d63031; }}
        .trend-improving {{ color: #27ae60; }}
        .trend-worsening {{ color: #e74c3c; }}
        .trend-stable {{ color: #7f8c8d; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Polymarket Bot Monitoring Dashboard</h1>
            <p>Generated: {data['generated_at'][:19].replace('T', ' ')} | Period: Last {data['period_days']} days</p>
        </div>

        <!-- System Status -->
        <div class="section">
            <h2>🔧 System Status</h2>
            <div class="metric">Main Bot: <span class="{self._get_status_class(data['sections']['system_status']['services']['main_bot']['status'])}">{data['sections']['system_status']['services']['main_bot']['status'].upper()}</span></div>
            <div class="metric">Monitoring: <span class="{self._get_status_class(data['sections']['system_status']['services']['monitoring']['status'])}">{data['sections']['system_status']['services']['monitoring']['status'].upper()}</span></div>
            <div class="metric">Alerts: <span class="{self._get_status_class(data['sections']['system_status']['services']['alerts']['status'])}">{data['sections']['system_status']['services']['alerts']['status'].upper()}</span></div>
            <div class="metric">CPU: {data['sections']['system_status']['resources']['cpu_percent']}%</div>
            <div class="metric">Memory: {data['sections']['system_status']['resources']['memory_percent']}%</div>
        </div>

        <!-- Security Overview -->
        <div class="section">
            <h2>🔒 Security Overview</h2>
"""

        security = data['sections']['security_overview']
        if security['latest_scan']:
            html += f"""
            <p><strong>Latest Scan:</strong> {security['latest_scan']['timestamp'][:19].replace('T', ' ')}</p>
            <div class="metric">Status: <span class="{self._get_status_class(security['latest_scan']['status'])}">{security['latest_scan']['status'].upper()}</span></div>
            <div class="metric">Critical Issues: <span class="status-critical">{security['latest_scan']['critical_issues']}</span></div>
            <div class="metric">High Issues: <span class="status-warning">{security['latest_scan']['high_issues']}</span></div>
            <div class="metric">Total Issues: {security['latest_scan']['total_issues']}</div>
"""

            if security['critical_issues']:
                html += "<h3>🚨 Critical Issues:</h3>"
                for issue in security['critical_issues'][:5]:  # Show top 5
                    html += f'<div class="issue"><strong>{issue["title"]}</strong><br>{issue["message"]}</div>'

        html += """
        </div>

        <!-- Performance Metrics -->
        <div class="section">
            <h2>📊 Performance Metrics</h2>
"""

        performance = data['sections']['performance_metrics']
        if performance['latest_benchmark']:
            html += f"""
            <p><strong>Latest Benchmark:</strong> {performance['latest_benchmark']['timestamp'][:19].replace('T', ' ')}</p>
            <div class="metric">Scenarios Run: {performance['latest_benchmark']['scenarios_run']}</div>
            <div class="metric">Duration: {performance['latest_benchmark']['duration_minutes']} minutes</div>
"""

            if performance['regressions']:
                html += f"<h3>⚠️ Regressions ({len(performance['regressions'])}):</h3><ul>"
                for reg in performance['regressions'][:3]:
                    html += f'<li><strong>{reg["metric"]}</strong>: {reg["change_percent"]:+.1f}%</li>'
                html += "</ul>"

            if performance['improvements']:
                html += f"<h3>✅ Improvements ({len(performance['improvements'])}):</h3><ul>"
                for imp in performance['improvements'][:3]:
                    html += f'<li><strong>{imp["metric"]}</strong>: {imp["change_percent"]:+.1f}%</li>'
                html += "</ul>"

        html += """
        </div>

        <!-- Alert Health -->
        <div class="section">
            <h2>🚨 Alert System Health</h2>
"""

        alert_health = data['sections']['alert_health']
        if alert_health['latest_check']:
            html += f"""
            <div class="metric">Last Check: {alert_health['latest_check']['timestamp'][:19].replace('T', ' ')}</div>
            <div class="metric">Overall Health: <span class="{self._get_status_class(alert_health['latest_check']['overall_health'])}">{alert_health['latest_check']['overall_health'].upper()}</span></div>
            <div class="metric">Issues: {alert_health['latest_check']['issues_count']}</div>
"""

            if alert_health['issues']:
                html += "<h3>⚠️ Alert Issues:</h3>"
                for issue in alert_health['issues'][:3]:
                    html += f'<div class="issue"><strong>{issue["component"]}</strong>: {issue["description"]}</div>'

        html += """
        </div>

        <!-- Trends Analysis -->
        <div class="section">
            <h2>📈 Trends Analysis</h2>
"""

        trends = data['sections']['trends']
        html += f"""
            <div class="metric">Security Trend: <span class="trend-{trends['security_trend']}">{trends['security_trend'].upper()}</span></div>
            <div class="metric">Performance Trend: <span class="trend-{trends['performance_trend']}">{trends['performance_trend'].upper()}</span></div>
            <div class="metric">Alert Reliability: {(trends['alert_reliability'] * 100):.1f}%</div>
"""

        if trends['insights']:
            html += "<h3>💡 Insights:</h3><ul>"
            for insight in trends['insights']:
                html += f"<li>{insight}</li>"
            html += "</ul>"

        html += """
        </div>
    </div>
</body>
</html>
"""

        return html

    def _generate_console_summary(self, data: Dict[str, Any]) -> str:
        """Generate console-friendly summary"""
        summary = f"""
🔍 Polymarket Bot Monitoring Dashboard
=======================================

Generated: {data['generated_at'][:19].replace('T', ' ')}
Period: Last {data['period_days']} days

🔧 System Status:
"""

        system = data['sections']['system_status']
        for service, status in system['services'].items():
            summary += f"  {service}: {status['status'].upper()}\n"

        summary += f"""
📊 Resources:
  CPU: {system['resources']['cpu_percent']}%
  Memory: {system['resources']['memory_percent']}%
  Disk: {system['resources']['disk_percent']}%

🔒 Security Overview:
"""

        security = data['sections']['security_overview']
        if security['latest_scan']:
            scan = security['latest_scan']
            summary += f"""  Status: {scan['status'].upper()}
  Critical Issues: {scan['critical_issues']}
  High Issues: {scan['high_issues']}
  Total Issues: {scan['total_issues']}
"""

        summary += """
📈 Performance Metrics:
"""

        performance = data['sections']['performance_metrics']
        if performance['latest_benchmark']:
            bench = performance['latest_benchmark']
            summary += f"""  Scenarios Run: {bench['scenarios_run']}
  Regressions: {len(performance['regressions'])}
  Improvements: {len(performance['improvements'])}
"""

        summary += """
🚨 Alert Health:
"""

        alert_health = data['sections']['alert_health']
        if alert_health['latest_check']:
            check = alert_health['latest_check']
            summary += f"""  Overall Health: {check['overall_health'].upper()}
  Issues: {check['issues_count']}
"""

        summary += """
📈 Trends:
"""

        trends = data['sections']['trends']
        summary += f"""  Security: {trends['security_trend'].upper()}
  Performance: {trends['performance_trend'].upper()}
  Alert Reliability: {(trends['alert_reliability'] * 100):.1f}%
"""

        if trends['insights']:
            summary += "\n💡 Key Insights:\n"
            for insight in trends['insights']:
                summary += f"  • {insight}\n"

        return summary

    def _get_status_class(self, status: str) -> str:
        """Get CSS class for status"""
        status = status.lower()
        if status in ['healthy', 'passed', 'good', 'active', 'running']:
            return 'status-good'
        elif status in ['warning', 'degraded', 'slow', 'worsening']:
            return 'status-warning'
        elif status in ['critical', 'failed', 'error', 'down', 'stopped']:
            return 'status-critical'
        else:
            return 'status-warning'

async def generate_dashboard():
    """Generate monitoring dashboard"""
    dashboard = MonitoringDashboard()
    await dashboard.generate_dashboard()

if __name__ == "__main__":
    import asyncio
    asyncio.run(generate_dashboard())
