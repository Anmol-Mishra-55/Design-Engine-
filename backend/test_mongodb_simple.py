#!/usr/bin/env python3
"""
MongoDB Atlas Connection Test - Windows Compatible
Tests connection to MongoDB Atlas with detailed diagnostics
"""
import asyncio
import logging
import os
import sys
import time
from urllib.parse import urlparse

try:
    import dns.resolver

    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    print("WARNING: dnspython not available, skipping DNS tests")

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# MongoDB Atlas connection string
MONGODB_URL = "mongodb+srv://blackholeinfiverse55_db_user:6SKTXNiidEZNTtDc@cluster0.acfgtzl.mongodb.net/?appName=Cluster0&retryWrites=true&w=majority"
DATABASE_NAME = "bhiv_db"


async def test_dns_resolution():
    """Test DNS resolution for MongoDB Atlas cluster"""
    print("\n[DNS] Testing DNS Resolution...")

    if not DNS_AVAILABLE:
        print("   [SKIP] DNS testing not available (install dnspython)")
        return True

    try:
        # Extract hostname from MongoDB URL
        parsed = urlparse(MONGODB_URL.replace("mongodb+srv://", "https://"))
        hostname = parsed.hostname

        if hostname:
            print(f"   Resolving: {hostname}")
            resolver = dns.resolver.Resolver()
            resolver.timeout = 10
            resolver.lifetime = 10

            # Try to resolve SRV record
            try:
                srv_records = resolver.resolve(f"_mongodb._tcp.{hostname}", "SRV")
                print(f"   [OK] SRV records found: {len(srv_records)} servers")
                for record in srv_records:
                    print(f"      - {record.target}:{record.port}")
            except Exception as e:
                print(f"   [FAIL] SRV resolution failed: {e}")

            # Try basic A record resolution
            try:
                a_records = resolver.resolve(hostname, "A")
                print(f"   [OK] A records found: {len(a_records)} IPs")
                for record in a_records:
                    print(f"      - {record}")
            except Exception as e:
                print(f"   [FAIL] A record resolution failed: {e}")

        return True
    except Exception as e:
        print(f"   [FAIL] DNS test failed: {e}")
        return False


async def test_basic_connection():
    """Test basic MongoDB connection"""
    print("\n[CONNECTION] Testing Basic MongoDB Connection...")

    try:
        # Create client with shorter timeout for testing
        client = AsyncIOMotorClient(
            MONGODB_URL,
            serverSelectionTimeoutMS=15000,  # 15 seconds
            connectTimeoutMS=15000,
            socketTimeoutMS=15000,
            maxPoolSize=1,
        )

        print("   Attempting to connect...")
        start_time = time.time()

        # Test connection with ping
        await client.admin.command("ping")

        connection_time = (time.time() - start_time) * 1000
        print(f"   [OK] Connection successful! ({connection_time:.2f}ms)")

        # Get server info
        try:
            server_info = await client.admin.command("buildInfo")
            print(f"   [INFO] MongoDB version: {server_info.get('version', 'unknown')}")
        except Exception as e:
            print(f"   [WARN] Could not get server info: {e}")

        # Test database access
        try:
            db = client[DATABASE_NAME]
            collections = await db.list_collection_names()
            print(f"   [INFO] Database '{DATABASE_NAME}' accessible with {len(collections)} collections")
        except Exception as e:
            print(f"   [WARN] Could not list collections: {e}")

        client.close()
        return True

    except ServerSelectionTimeoutError as e:
        print(f"   [FAIL] Server selection timeout: {e}")
        print("   [INFO] This usually indicates network connectivity issues")
        return False
    except ConnectionFailure as e:
        print(f"   [FAIL] Connection failure: {e}")
        return False
    except Exception as e:
        print(f"   [FAIL] Unexpected error: {e}")
        return False


async def test_network_connectivity():
    """Test network connectivity to MongoDB Atlas"""
    print("\n[NETWORK] Testing Network Connectivity...")

    try:
        import socket

        # Test connectivity to MongoDB Atlas
        hostname = "cluster0.acfgtzl.mongodb.net"
        port = 27017

        print(f"   Testing connection to {hostname}:{port}")

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)

        try:
            result = sock.connect_ex((hostname, port))
            if result == 0:
                print(f"   [OK] Port {port} is reachable")
                return True
            else:
                print(f"   [FAIL] Port {port} is not reachable (error code: {result})")
                return False
        finally:
            sock.close()

    except Exception as e:
        print(f"   [FAIL] Network test failed: {e}")
        return False


async def test_authentication():
    """Test MongoDB authentication"""
    print("\n[AUTH] Testing Authentication...")

    try:
        client = AsyncIOMotorClient(MONGODB_URL, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000, maxPoolSize=1)

        # Try to access admin database (requires authentication)
        admin_db = client.admin
        result = await admin_db.command("ping")

        if result.get("ok") == 1:
            print("   [OK] Authentication successful")

            # Try to list databases
            try:
                db_list = await client.list_database_names()
                print(f"   [INFO] Accessible databases: {db_list}")
            except Exception as e:
                print(f"   [WARN] Could not list databases: {e}")

            client.close()
            return True
        else:
            print("   [FAIL] Authentication failed")
            client.close()
            return False

    except Exception as e:
        print(f"   [FAIL] Authentication test failed: {e}")
        return False


async def comprehensive_test():
    """Run comprehensive MongoDB Atlas connection test"""
    print("=" * 60)
    print("MongoDB Atlas Connection Diagnostic Test")
    print("=" * 60)

    tests = [
        ("DNS Resolution", test_dns_resolution),
        ("Network Connectivity", test_network_connectivity),
        ("Basic Connection", test_basic_connection),
        ("Authentication", test_authentication),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            results[test_name] = await test_func()
        except Exception as e:
            print(f"   [FAIL] {test_name} failed with exception: {e}")
            results[test_name] = False

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    all_passed = True
    for test_name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"   {status} {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("SUCCESS: All tests passed! MongoDB Atlas connection is working.")
        print("INFO: Your server should be able to connect to MongoDB Atlas.")
    else:
        print("WARNING: Some tests failed. Check the issues above.")
        print("\nTroubleshooting Tips:")
        print("   1. Check your internet connection")
        print("   2. Verify MongoDB Atlas cluster is running")
        print("   3. Check firewall settings (allow outbound port 27017)")
        print("   4. Verify credentials in connection string")
        print("   5. Check MongoDB Atlas IP whitelist settings")
        print("   6. Try connecting from MongoDB Compass or mongo shell")

    print("=" * 60)
    return all_passed


if __name__ == "__main__":
    try:
        result = asyncio.run(comprehensive_test())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nTest failed with exception: {e}")
        sys.exit(1)
