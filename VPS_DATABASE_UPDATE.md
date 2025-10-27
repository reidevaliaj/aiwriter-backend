# 🗄️ VPS Database Update Guide

## 🎯 **Quick VPS Database Update**

You need to update the VPS database to add the `callback_url` field. Here's how:

### **Step 1: Upload New Code to VPS**
```bash
# Upload the new migration file to VPS
scp backend/alembic/versions/002_add_callback_url.py rei@142.93.161.58:/home/rei/apps/aiwriter-backend/alembic/versions/
```

### **Step 2: Run Database Migration on VPS**
```bash
# SSH into VPS
ssh rei@142.93.161.58

# Navigate to backend directory
cd /home/rei/apps/aiwriter-backend

# Activate virtual environment
source venv/bin/activate

# Check current migration status
alembic current

# Run the new migration
alembic upgrade head

# Restart backend service
sudo systemctl restart aiwriter

# Check service status
sudo systemctl status aiwriter
```

### **Step 3: Verify Update**
```bash
# Check if callback_url field was added
sudo -u postgres psql -d aiwriter -c "\d sites"

# Should show callback_url column
```

## 🔧 **Alternative: Manual SQL Update**

If Alembic isn't working, you can run this SQL directly:

```sql
-- Connect to database
sudo -u postgres psql -d aiwriter

-- Add callback_url column
ALTER TABLE sites ADD COLUMN callback_url VARCHAR;

-- Verify the change
\d sites
```

## 📋 **What This Migration Does**

- ✅ **Adds `callback_url` field** to sites table
- ✅ **Field is nullable** (won't break existing data)
- ✅ **Stores WordPress callback URLs** for webhook communication
- ✅ **Enables proper REST API communication**

## 🎯 **Expected Result**

After the migration:
- ✅ Sites table will have `callback_url` column
- ✅ Backend will store WordPress callback URLs
- ✅ Article generation will use stored URLs
- ✅ Fallback retry logic will work properly

## 🚨 **Important Notes**

1. **Backup First**: Always backup database before migrations
2. **Test Locally**: Test migration on development first
3. **Monitor Logs**: Check backend logs after restart
4. **Verify Functionality**: Test article generation after update

## 🔍 **Troubleshooting**

### **If Migration Fails**
```bash
# Check migration status
alembic current

# Check migration history
alembic history

# Rollback if needed
alembic downgrade -1
```

### **If Service Won't Start**
```bash
# Check service logs
sudo journalctl -u aiwriter -f

# Check database connection
sudo -u postgres psql -d aiwriter -c "SELECT 1;"
```

The database update will enable proper WordPress REST API communication! 🚀

