#!/usr/bin/env python3
"""
MongoDB Atlas Connection Troubleshooter
Diagnoses and fixes Atlas connection issues
"""

import socket
import subprocess
import sys
import time
from urllib.parse import urlparse

def test_dns_resolution():
    """Test DNS resolution for MongoDB Atlas"""
    print("🔍 Testing DNS Resolution...")

    hostnames = [
        "ac-xqai9lp-shard-00-00.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-01.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-02.acfgtzl.mongodb.net"
    ]

    for hostname in hostnames:
        try:
            ip = socket.gethostbyname(hostname)
            print(f"  ✅ {hostname} -> {ip}")
        except socket.gaierror as e:
            print(f"  ❌ {hostname} -> DNS Error: {e}")
            return False

    return True

def test_port_connectivity():
    """Test port 27017 connectivity"""
    print("\n🔍 Testing Port Connectivity...")

    hostnames = [
        "ac-xqai9lp-shard-00-00.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-01.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-02.acfgtzl.mongodb.net"
    ]

    for hostname in hostnames:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((hostname, 27017))
            sock.close()

            if result == 0:
                print(f"  ✅ {hostname}:27017 - Connected")
            else:
                print(f"  ❌ {hostname}:27017 - Connection failed")
                return False
        except Exception as e:
            print(f"  ❌ {hostname}:27017 - Error: {e}")
            return False

    return True

def test_mongodb_connection():
    """Test actual MongoDB connection"""
    print("\n🔍 Testing MongoDB Connection...")

    try:
        import pymongo

        atlas_url = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"

        client = pymongo.MongoClient(atlas_url, serverSelectionTimeoutMS=10000)
        client.admin.command('ping')
        client.close()

        print("  ✅ MongoDB Atlas connection successful!")
        return True

    except Exception as e:
        print(f"  ❌ MongoDB connection failed: {e}")
        return False

def check_firewall_issues():
    """Check for common firewall issues"""
    print("\n🔍 Checking Firewall Issues...")

    # Check if running on corporate network
    try:
        # Try to connect to a known external service
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("8.8.8.8", 53))
        sock.close()

        if result != 0:
            print("  ⚠️  External connectivity issues detected")
            print("     - You may be on a corporate network with restrictions")
            print("     - Contact your network administrator")
            return False
        else:
            print("  ✅ External connectivity OK")

    except Exception as e:
        print(f"  ⚠️  Network test failed: {e}")

    return True

def suggest_solutions():
    """Suggest solutions based on test results"""
    print("\n🔧 Suggested Solutions:")
    print("=" * 40)

    print("1. Use Local MongoDB (Recommended for development):")
    print("   python setup_mongodb.py")
    print("")

    print("2. Fix Network Issues:")
    print("   - Check if you're on a corporate network")
    print("   - Try different internet connection (mobile hotspot)")
    print("   - Contact network administrator about MongoDB Atlas access")
    print("")

    print("3. MongoDB Atlas Troubleshooting:")
    print("   - Check Atlas cluster status in MongoDB Atlas dashboard")
    print("   - Verify IP whitelist includes your current IP")
    print("   - Try different Atlas region/cluster")
    print("")

    print("4. Continue without database:")
    print("   - Server will start but some features disabled")
    print("   - Good for testing API endpoints")

def main():
    """Main troubleshooting function"""
    print("🔧 MongoDB Atlas Connection Troubleshooter")
    print("=" * 50)

    # Run diagnostic tests
    dns_ok = test_dns_resolution()
    port_ok = test_port_connectivity() if dns_ok else False
    mongo_ok = test_mongodb_connection() if port_ok else False
    firewall_ok = check_firewall_issues()

    print("\n📊 Diagnostic Results:")
    print("=" * 30)
    print(f"DNS Resolution: {'✅ PASS' if dns_ok else '❌ FAIL'}")
    print(f"Port Connectivity: {'✅ PASS' if port_ok else '❌ FAIL'}")
    print(f"MongoDB Connection: {'✅ PASS' if mongo_ok else '❌ FAIL'}")
    print(f"Network/Firewall: {'✅ PASS' if firewall_ok else '⚠️  ISSUES'}")

    if mongo_ok:
        print("\n🎉 MongoDB Atlas connection is working!")
        print("The issue may be intermittent. Try restarting your server.")
    else:
        suggest_solutions()

if __name__ == "__main__":
    main()
