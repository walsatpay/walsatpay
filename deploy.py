#!/usr/bin/env python3
"""
WasatPay Deployment Script
Prepares the application for production deployment
"""

import os
import shutil
import sys

def prepare_for_production():
    """Prepare application for production deployment"""
    print("🚀 Preparing WasatPay for production deployment...")
    
    # Replace main.py with production version
    main_path = os.path.join('src', 'main.py')
    production_main_path = os.path.join('src', 'main_production.py')
    
    if os.path.exists(production_main_path):
        # Backup original main.py
        backup_path = os.path.join('src', 'main_development.py')
        if os.path.exists(main_path):
            shutil.copy2(main_path, backup_path)
            print(f"✅ Backed up original main.py to {backup_path}")
        
        # Replace with production version
        shutil.copy2(production_main_path, main_path)
        print(f"✅ Replaced main.py with production version")
    else:
        print(f"❌ Production main file not found: {production_main_path}")
        return False
    
    # Create necessary directories
    directories = [
        'src/static',
        'src/static/assets',
        'src/static/assets/images',
        'uploads',
        'logs'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Created directory: {directory}")
    
    # Copy logo to static assets
    logo_source = os.path.join('src', 'static', 'assets', 'images', 'wasat-logo-official.png')
    if os.path.exists(logo_source):
        print(f"✅ Wasat logo found at {logo_source}")
    else:
        print(f"⚠️  Wasat logo not found at {logo_source}")
    
    # Check required files
    required_files = [
        'requirements.txt',
        'gunicorn_config.py',
        '.do/app.yaml',
        'src/config.py'
    ]
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ Required file found: {file_path}")
        else:
            print(f"❌ Required file missing: {file_path}")
            return False
    
    print("\n🎉 Production preparation completed successfully!")
    print("\nNext steps:")
    print("1. Commit all changes to your Git repository")
    print("2. Push to GitHub")
    print("3. Deploy to DigitalOcean App Platform")
    print("4. Configure environment variables")
    print("5. Set up domain and SSL")
    
    return True

def restore_development():
    """Restore development configuration"""
    print("🔄 Restoring development configuration...")
    
    main_path = os.path.join('src', 'main.py')
    backup_path = os.path.join('src', 'main_development.py')
    
    if os.path.exists(backup_path):
        shutil.copy2(backup_path, main_path)
        print(f"✅ Restored development main.py from {backup_path}")
    else:
        print(f"❌ Development backup not found: {backup_path}")
        return False
    
    print("✅ Development configuration restored")
    return True

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        restore_development()
    else:
        prepare_for_production()

