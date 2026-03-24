#!/usr/bin/env python3
"""
Network Troubleshooting Script for MongoDB Atlas
Helps diagnose and fix network connectivity issues
"""
import os
import subprocess
import sys
import time


def run_command(command, description):
    """Run a command and return the result"""
    print(f"\n[INFO] {description}")
    print(f"[CMD] {command}")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
        if result.stdout:
            print(f"[OUT] {result.stdout.strip()}")
        if result.stderr:
            print(f"[ERR] {result.stderr.strip()}")
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("[TIMEOUT] Command timed out")
        return False
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def check_internet_connectivity():
    """Check basic internet connectivity"""
    print("\n" + "=" * 60)
    print("CHECKING INTERNET CONNECTIVITY")
    print("=" * 60)

    # Test basic connectivity
    sites = ["8.8.8.8", "google.com", "cloudflare.com"]
    for site in sites:
        success = run_command(f"ping -n 2 {site}", f"Testing connectivity to {site}")
        if success:
            print(f"[OK] Can reach {site}")
            return True
        else:
            print(f"[FAIL] Cannot reach {site}")

    print("[CRITICAL] No internet connectivity detected!")
    return False


def check_dns_configuration():
    """Check and potentially fix DNS configuration"""
    print("\n" + "=" * 60)
    print("CHECKING DNS CONFIGURATION")
    print("=" * 60)

    # Check current DNS servers
    run_command('ipconfig /all | findstr "DNS Servers"', "Current DNS servers")

    # Test DNS resolution with different servers
    dns_servers = ["8.8.8.8", "1.1.1.1", "208.67.222.222"]

    for dns in dns_servers:
        print(f"\n[TEST] Testing DNS resolution with {dns}")
        success = run_command(f"nslookup google.com {dns}", f"DNS test with {dns}")
        if success:
            print(f"[OK] DNS {dns} is working")
        else:
            print(f"[FAIL] DNS {dns} is not working")


def flush_dns_cache():
    """Flush DNS cache"""
    print("\n" + "=" * 60)
    print("FLUSHING DNS CACHE")
    print("=" * 60)

    commands = [
        ("ipconfig /flushdns", "Flush Windows DNS cache"),
        ("ipconfig /registerdns", "Re-register DNS"),
        ("ipconfig /release", "Release IP configuration"),
        ("ipconfig /renew", "Renew IP configuration"),
    ]

    for cmd, desc in commands:
        try:
            run_command(cmd, desc)
            time.sleep(2)
        except Exception as e:
            print(f"[WARN] {desc} failed: {e}")


def check_firewall_settings():
    """Check Windows Firewall settings"""
    print("\n" + "=" * 60)
    print("CHECKING FIREWALL SETTINGS")
    print("=" * 60)

    # Check if Windows Firewall is blocking outbound connections
    run_command("netsh advfirewall show allprofiles state", "Windows Firewall status")

    # Check for MongoDB-related firewall rules
    run_command("netsh advfirewall firewall show rule name=all | findstr -i mongo", "MongoDB firewall rules")


def test_mongodb_connectivity():
    """Test MongoDB Atlas connectivity"""
    print("\n" + "=" * 60)
    print("TESTING MONGODB ATLAS CONNECTIVITY")
    print("=" * 60)

    # Test connectivity to MongoDB Atlas servers
    mongodb_servers = [
        "ac-xqai9lp-shard-00-00.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-01.acfgtzl.mongodb.net",
        "ac-xqai9lp-shard-00-02.acfgtzl.mongodb.net",
    ]

    for server in mongodb_servers:
        print(f"\n[TEST] Testing connectivity to {server}")

        # Test DNS resolution
        run_command(f"nslookup {server}", f"DNS resolution for {server}")

        # Test ping
        run_command(f"ping -n 2 {server}", f"Ping test to {server}")

        # Test port connectivity (if telnet is available)
        run_command(f"telnet {server} 27017", f"Port 27017 test to {server}")


def suggest_fixes():
    """Suggest potential fixes"""
    print("\n" + "=" * 60)
    print("SUGGESTED FIXES")
    print("=" * 60)

    fixes = [
        "1. Change DNS servers to Google DNS (8.8.8.8, 8.8.4.4)",
        "2. Temporarily disable Windows Firewall for testing",
        "3. Check if your ISP is blocking MongoDB ports",
        "4. Try connecting from a different network (mobile hotspot)",
        "5. Contact your network administrator if on corporate network",
        "6. Check MongoDB Atlas IP whitelist settings",
        "7. Try using MongoDB Compass to test connection",
        "8. Consider using a VPN if there are regional restrictions",
    ]

    for fix in fixes:
        print(f"   {fix}")


def change_dns_to_google():
    """Change DNS servers to Google DNS"""
    print("\n" + "=" * 60)
    print("CHANGING DNS TO GOOGLE DNS")
    print("=" * 60)

    print("[INFO] This will change your DNS servers to Google DNS (8.8.8.8, 8.8.4.4)")
    print("[WARN] This requires administrator privileges")

    # Get network interface name
    result = subprocess.run("netsh interface show interface", shell=True, capture_output=True, text=True)
    print("[INFO] Available network interfaces:")
    print(result.stdout)

    interface_name = input("\nEnter the name of your active network interface (e.g., 'Wi-Fi' or 'Ethernet'): ").strip()

    if interface_name:
        commands = [
            f'netsh interface ip set dns "{interface_name}" static 8.8.8.8',
            f'netsh interface ip add dns "{interface_name}" 8.8.4.4 index=2',
        ]

        for cmd in commands:
            success = run_command(cmd, f"Setting DNS: {cmd}")
            if not success:
                print("[ERROR] Failed to set DNS. Make sure you're running as administrator.")
                return False

        print("[SUCCESS] DNS servers changed to Google DNS")
        print("[INFO] Flushing DNS cache...")
        run_command("ipconfig /flushdns", "Flush DNS cache")
        return True

    return False


def main():
    """Main troubleshooting function"""
    print("MongoDB Atlas Network Troubleshooting Tool")
    print("=" * 60)

    # Check if running as administrator
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        import ctypes

        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0

    if not is_admin:
        print("[WARN] Not running as administrator. Some fixes may not work.")

    # Run diagnostics
    steps = [
        ("Internet Connectivity", check_internet_connectivity),
        ("DNS Configuration", check_dns_configuration),
        ("MongoDB Connectivity", test_mongodb_connectivity),
        ("Firewall Settings", check_firewall_settings),
    ]

    results = {}
    for step_name, step_func in steps:
        try:
            results[step_name] = step_func()
        except Exception as e:
            print(f"[ERROR] {step_name} failed: {e}")
            results[step_name] = False

    # Show results
    print("\n" + "=" * 60)
    print("DIAGNOSTIC RESULTS")
    print("=" * 60)

    for step_name, success in results.items():
        status = "[PASS]" if success else "[FAIL]"
        print(f"   {status} {step_name}")

    # Suggest fixes
    suggest_fixes()

    # Offer to apply fixes
    print("\n" + "=" * 60)
    print("AUTOMATIC FIXES")
    print("=" * 60)

    if not results.get("Internet Connectivity", False):
        print("[CRITICAL] No internet connectivity. Check your network connection first.")
        return

    apply_fixes = input("\nWould you like to apply automatic fixes? (y/n): ").lower().strip()

    if apply_fixes == "y":
        print("\n[INFO] Applying fixes...")

        # Flush DNS cache
        flush_dns_cache()

        # Offer to change DNS
        change_dns = input("\nChange DNS servers to Google DNS? (y/n): ").lower().strip()
        if change_dns == "y":
            change_dns_to_google()

        print("\n[INFO] Fixes applied. Please test your MongoDB connection again.")
        print("[INFO] You may need to restart your application or computer.")

    print("\n[INFO] Troubleshooting complete.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[INFO] Troubleshooting interrupted by user.")
    except Exception as e:
        print(f"\n[ERROR] Troubleshooting failed: {e}")
