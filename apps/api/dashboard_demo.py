"""
Dashboard Demo Script for Logforge M7 Enterprise Platform
Shows how to access and interact with the 6 pre-built enterprise dashboards
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import sys
import argparse


class LogforgeDashboardDemo:
    """Demo client for Logforge enterprise dashboards"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def check_api_health(self) -> bool:
        """Check if Logforge API is running"""
        try:
            response = self.session.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Logforge API is running (Status: {health_data['status']})")
                return True
            else:
                print(f"❌ API health check failed: {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Logforge API at {self.base_url}")
            print(f"   Error: {e}")
            print(f"   Make sure the API is running: docker compose up -d")
            return False
    
    def list_dashboards(self) -> List[Dict[str, Any]]:
        """Get list of available dashboards"""
        try:
            response = self.session.get(f"{self.base_url}/v1/dashboards")
            response.raise_for_status()
            
            data = response.json()
            dashboards = data.get("dashboards", [])
            
            print(f"\n📊 Available Enterprise Dashboards ({len(dashboards)}):")
            print("=" * 60)
            
            for i, dashboard in enumerate(dashboards, 1):
                print(f"{i}. {dashboard['name']} ({dashboard['id']})")
                print(f"   Type: {dashboard['type']}")
                print(f"   Description: {dashboard['description']}")
                print(f"   Widgets: {dashboard['widget_count']}")
                print(f"   Tags: {', '.join(dashboard['tags'])}")
                print()
            
            return dashboards
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch dashboards: {e}")
            return []
    
    def get_dashboard_definition(self, dashboard_id: str) -> Dict[str, Any]:
        """Get dashboard definition with widgets"""
        try:
            response = self.session.get(f"{self.base_url}/v1/dashboards/{dashboard_id}")
            response.raise_for_status()
            
            dashboard = response.json()
            
            print(f"\n🔧 Dashboard Definition: {dashboard['name']}")
            print("=" * 60)
            print(f"ID: {dashboard['id']}")
            print(f"Type: {dashboard['type']}")
            print(f"Description: {dashboard['description']}")
            print(f"Widgets: {len(dashboard['widgets'])}")
            
            print("\nWidgets:")
            for widget in dashboard['widgets']:
                print(f"  • {widget['title']} ({widget['type']})")
                pos = widget['position']
                print(f"    Position: x={pos['x']}, y={pos['y']}, w={pos['w']}, h={pos['h']}")
            
            return dashboard
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch dashboard definition: {e}")
            return {}
    
    def get_dashboard_data(self, dashboard_id: str, hours_back: int = 24) -> Dict[str, Any]:
        """Get real-time dashboard data"""
        try:
            # Calculate time range
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours_back)
            
            params = {
                "start_time": start_time.isoformat() + "Z",
                "end_time": end_time.isoformat() + "Z"
            }
            
            print(f"\n📈 Generating Dashboard Data: {dashboard_id}")
            print(f"Time Range: Last {hours_back} hours")
            print("=" * 60)
            
            start = time.time()
            response = self.session.get(
                f"{self.base_url}/v1/dashboards/{dashboard_id}/data",
                params=params
            )
            response.raise_for_status()
            execution_time = (time.time() - start) * 1000
            
            dashboard_data = response.json()
            
            print(f"⚡ Generated in {execution_time:.1f}ms")
            print(f"Dashboard: {dashboard_data['dashboard_id']}")
            print(f"Generated at: {dashboard_data['generated_at']}")
            print(f"Total widgets: {dashboard_data['metadata']['total_widgets']}")
            
            print("\nWidget Data:")
            for widget_id, widget_data in dashboard_data['widgets'].items():
                self._display_widget_data(widget_id, widget_data)
            
            return dashboard_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch dashboard data: {e}")
            return {}
    
    def _display_widget_data(self, widget_id: str, widget_data: Dict[str, Any]):
        """Display formatted widget data"""
        print(f"\n  📊 {widget_data['title']} ({widget_data['type']})")
        
        if "error" in widget_data:
            print(f"    ❌ Error: {widget_data['error']}")
            return
        
        data = widget_data.get("data", {})
        
        if widget_data["type"] == "metric":
            value = data.get("value", "N/A")
            label = data.get("label", "")
            print(f"    Value: {value:,} {label}")
            
        elif widget_data["type"] == "line_chart":
            series = data.get("series", [])
            if series:
                series_data = series[0].get("data", [])
                print(f"    Data points: {len(series_data)}")
                if series_data:
                    latest = series_data[-1]
                    print(f"    Latest: {latest.get('y', 'N/A')} at {latest.get('x', 'N/A')}")
                    
        elif widget_data["type"] == "bar_chart":
            categories = data.get("categories", [])
            series = data.get("series", [])
            if categories and series:
                print(f"    Categories: {len(categories)}")
                print(f"    Top 3: {categories[:3]}")
                
        elif widget_data["type"] == "pie_chart":
            series = data.get("series", [])
            if series:
                print(f"    Segments: {len(series)}")
                top_3 = sorted(series, key=lambda x: x.get("value", 0), reverse=True)[:3]
                for segment in top_3:
                    print(f"      • {segment.get('label', 'N/A')}: {segment.get('value', 0)}")
                    
        elif widget_data["type"] == "table":
            rows = data.get("rows", [])
            columns = data.get("columns", [])
            print(f"    Rows: {len(rows)}, Columns: {len(columns)}")
            
        else:
            print(f"    Raw data: {json.dumps(data, default=str)[:100]}...")
        
        if "execution_time_ms" in widget_data:
            print(f"    Query time: {widget_data['execution_time_ms']:.1f}ms")
    
    def get_widget_data(self, dashboard_id: str, widget_id: str) -> Dict[str, Any]:
        """Get data for specific widget"""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/dashboards/{dashboard_id}/widgets/{widget_id}/data"
            )
            response.raise_for_status()
            
            widget_response = response.json()
            
            print(f"\n🔍 Widget Data: {widget_id}")
            print("=" * 60)
            
            widget_data = widget_response["widget_data"]
            self._display_widget_data(widget_id, widget_data)
            
            return widget_response
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch widget data: {e}")
            return {}
    
    def demo_all_dashboards(self, hours_back: int = 24):
        """Demo all available dashboards"""
        print("🚀 Starting Logforge Enterprise Dashboard Demo")
        print("=" * 60)
        
        if not self.check_api_health():
            return
        
        dashboards = self.list_dashboards()
        if not dashboards:
            return
        
        print(f"\n🔄 Generating data for all {len(dashboards)} dashboards...")
        
        for i, dashboard in enumerate(dashboards, 1):
            print(f"\n{'='*60}")
            print(f"Demo {i}/{len(dashboards)}: {dashboard['name']}")
            print(f"{'='*60}")
            
            # Get dashboard definition
            self.get_dashboard_definition(dashboard['id'])
            
            # Generate dashboard data
            self.get_dashboard_data(dashboard['id'], hours_back)
            
            # Small delay between dashboards
            if i < len(dashboards):
                time.sleep(1)
        
        print(f"\n✅ Demo completed! All {len(dashboards)} enterprise dashboards ready.")
        print("\n📖 Available Dashboard IDs:")
        for dashboard in dashboards:
            print(f"   • {dashboard['id']} - {dashboard['name']}")
        
        print(f"\n🌐 Access dashboards at:")
        print(f"   • API Docs: {self.base_url}/docs")
        print(f"   • Dashboard List: {self.base_url}/v1/dashboards")
        print(f"   • Example: {self.base_url}/v1/dashboards/security/data")
    
    def demo_specific_dashboard(self, dashboard_id: str, hours_back: int = 24):
        """Demo specific dashboard"""
        print(f"🎯 Logforge Dashboard Demo: {dashboard_id}")
        print("=" * 60)
        
        if not self.check_api_health():
            return
        
        # Get dashboard definition
        dashboard_def = self.get_dashboard_definition(dashboard_id)
        if not dashboard_def:
            return
        
        # Generate dashboard data
        dashboard_data = self.get_dashboard_data(dashboard_id, hours_back)
        if not dashboard_data:
            return
        
        print(f"\n✅ Dashboard '{dashboard_id}' demo completed!")
        print(f"🌐 Access at: {self.base_url}/v1/dashboards/{dashboard_id}/data")


def main():
    """Main demo function"""
    parser = argparse.ArgumentParser(description="Logforge Enterprise Dashboard Demo")
    parser.add_argument("--url", default="http://localhost:8080", 
                       help="Logforge API base URL (default: http://localhost:8080)")
    parser.add_argument("--dashboard", 
                       choices=["security", "performance", "infrastructure", "business", "compliance", "executive"],
                       help="Demo specific dashboard")
    parser.add_argument("--hours", type=int, default=24,
                       help="Hours of data to query (default: 24)")
    parser.add_argument("--list-only", action="store_true",
                       help="Only list available dashboards")
    
    args = parser.parse_args()
    
    demo = LogforgeDashboardDemo(args.url)
    
    if args.list_only:
        demo.check_api_health()
        demo.list_dashboards()
    elif args.dashboard:
        demo.demo_specific_dashboard(args.dashboard, args.hours)
    else:
        demo.demo_all_dashboards(args.hours)


if __name__ == "__main__":
    main()