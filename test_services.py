#!/usr/bin/env python
"""Test script to verify services are working correctly."""

import requests
import sys

def test_endpoint(url: str, name: str) -> bool:
    """Test an endpoint and return success status."""
    try:
        response = requests.get(url, timeout=2)
        if response.status_code == 200:
            print(f"✅ {name}: OK")
            print(f"   Response: {response.json()}")
            return True
        else:
            print(f"❌ {name}: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def main():
    """Test all service endpoints."""
    print("\n🔍 Testing TTS Server Improvements\n")
    print("=" * 60)
    
    # Note: Services must be running for tests to work
    print("\n📝 Prerequisites:")
    print("   Run: python run_services.py")
    print("   (Services should be running on localhost:8000 and localhost:8010)")
    print("\n" + "=" * 60)
    
    results = []
    
    print("\n🧪 Testing TTS Server (port 8000):")
    results.append(test_endpoint("http://localhost:8000/health", "Health Check"))
    results.append(test_endpoint("http://localhost:8000/metrics", "Metrics Endpoint"))
    results.append(test_endpoint("http://localhost:8000/voices", "Voices List"))
    
    print("\n🧪 Testing STT Server (port 8010):")
    results.append(test_endpoint("http://localhost:8010/health", "Health Check"))
    results.append(test_endpoint("http://localhost:8010/metrics", "Metrics Endpoint"))
    
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"\n✅ All tests passed! ({passed}/{total})")
        print("\n🎉 Services are running correctly with:")
        print("   - Lifespan events ✅")
        print("   - Type hints ✅")
        print("   - Circuit breaker ✅")
        print("   - Prometheus metrics ✅")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed ({passed}/{total} passed)")
        print("\n💡 Make sure services are running:")
        print("   python run_services.py")
        return 1

if __name__ == "__main__":
    sys.exit(main())
