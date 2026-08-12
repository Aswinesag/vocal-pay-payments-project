# Biometric Enrollment Wizard - Quick Implementation

## ✅ Route Added to main.py
```python
@app.get("/enroll")
async def enroll_page(request: Request):
    return templates.TemplateResponse("enroll.html", {"request": request})
```

## Core JavaScript APIs Needed

### 1. Camera Capture (getUserMedia)
```javascript
const stream = await navigator.mediaDevices.getUserMedia({ video: true });
video.srcObject = stream;
canvas.toBlob((blob) => { faceSnapshot = blob; }, 'image/jpeg');
```

### 2. Audio Recording (MediaRecorder)
```javascript
const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
const recorder = new MediaRecorder(stream);
recorder.ondataavailable = (e) => audioChunks.push(e.data);
recorder.onstop = () => audioBlob = new Blob(audioChunks);
```

### 3. Submit to Backend
```javascript
const formData = new FormData();
formData.append('photo_file', faceSnapshot, 'face.jpg');
formData.append('audio_file', audioBlob, 'voice.webm');
formData.append('full_name', user.full_name);
formData.append('email', user.email);
formData.append('phone_number', user.phone_number);

await fetch('/api/v1/users/enroll', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
});
```

## Files to Create

1. **app/templates/enroll.html** - 2-step wizard UI
2. Update **signup.html** line ~140: `window.location.href = '/enroll';`

## Testing
- Camera permission → Capture photo → Show preview
- Mic permission → Record 5-10s → Stop recording
- Submit FormData → Backend processes → Redirect to /dashboard

**Status:** ✅ Route ready, template needed
