# 🗄️ Alembic Database Migration Setup

## 🎯 **Goal: Proper Alembic Workflow for VPS Database Updates**

You need Alembic working so you can easily update the VPS database. Let me set this up properly.

## 🔍 **Current Problem**

- ✅ **Alembic files exist** but not properly configured
- ❌ **Alembic not installed** in current environment
- ❌ **Mixed approach** (Alembic + manual SQL)
- ❌ **No migration workflow** for VPS updates

## 🚀 **Solution: Proper Alembic Setup**

### **Step 1: Install Alembic (if not installed)**
```bash
# On VPS (where backend is running)
cd /home/rei/apps/aiwriter-backend
source venv/bin/activate
pip install alembic
```

### **Step 2: Create Missing Migration for callback_url**
Since we added `callback_url` field to the Site model, we need a migration:

```bash
# On VPS
alembic revision --autogenerate -m "Add callback_url to sites table"
alembic upgrade head
```

### **Step 3: VPS Database Update Workflow**
```bash
# 1. Upload new code to VPS
# 2. Activate virtual environment
cd /home/rei/apps/aiwriter-backend
source venv/bin/activate

# 3. Run migrations
alembic upgrade head

# 4. Restart backend service
sudo systemctl restart aiwriter
```

## 📋 **Migration Files Needed**

### **Current Migration: 001_initial_schema.py**
- ✅ Creates all initial tables
- ✅ Has all the basic schema

### **New Migration Needed: 002_add_callback_url.py**
- ✅ Adds `callback_url` field to sites table
- ✅ Handles existing data (nullable field)

## 🔧 **Manual Migration Creation**

Since Alembic isn't working locally, let me create the migration manually:
