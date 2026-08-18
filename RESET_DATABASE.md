# Database Reset Instructions

## ✅ Quick Reset (When Server is STOPPED)

### Step 1: Stop the Server
```bash
# Press Ctrl+C in the terminal where uvicorn is running
```

### Step 2: Delete the Database File
```bash
del vocalpay.db
```

### Step 3: Restart the Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The database will be automatically recreated empty on startup!

---

## 🔧 Reset While Server is Running

If you can't stop the server, use this Python script:

```bash
python clear_database.py
```

This will delete all users while keeping the database structure intact.

---

## 📊 Verify Database Status

Check if the database is clean:

```bash
python verify_database.py
```

Should show:
```
✅ Database is CLEAN - Ready for fresh signups!
```

---

## Current Status

The database currently has **2 user records** that need to be removed.

**Solution:**
1. **STOP the uvicorn server** (Ctrl+C)
2. **Delete vocalpay.db file**
3. **Restart the server**

That's it! Fresh database ready for new signups.
