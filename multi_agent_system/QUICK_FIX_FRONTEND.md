# Quick Fix: Frontend Not Sending Conversation State

## Problem

When you provide info one-by-one (like "Name: John Doe"), the system consults specialist agents instead of continuing the OT form conversation. This happens because the frontend isn't sending the conversation state back to the backend.

## Solution: Update Frontend JavaScript

Open [frontend/chatbotui/index.html](../frontend/chatbotui/index.html) and make these 3 changes:

### Change 1: Add State Storage Variable (Line ~418)

Find:
```javascript
let socket = null;
const WS_URL = 'ws://localhost:8082/ws/query';
let currentMessageId = null;
let isGenerating = false;
let isConnected = false;
```

Add this line after `isConnected`:
```javascript
let conversationState = null;  // Store OT conversation state
```

### Change 2: Store State from Backend (Line ~559)

Find the `case 'complete':` in the `handleStreamEvent` function:
```javascript
case 'complete':
    finishResponse(event.data.final_answer);
    collapseThinking();
    break;
```

Change it to:
```javascript
case 'complete':
    finishResponse(event.data.final_answer);
    collapseThinking();
    // Store conversation state for multi-turn
    conversationState = {
        ot_conversation_state: event.data.ot_conversation_state,
        ot_conversation_active: event.data.ot_conversation_active
    };
    console.log('💾 Stored conversation state:', conversationState);
    break;
```

### Change 3: Send State Back to Backend (Line ~783)

Find the `sendMessage` function where it sends to the WebSocket:
```javascript
// Send to server
socket.send(JSON.stringify({ query: text }));
```

Change it to:
```javascript
// Send to server with conversation state
const payload = { query: text };

// Include previous state if OT conversation is active
if (conversationState && conversationState.ot_conversation_active) {
    payload.previous_state = conversationState;
    console.log('📤 Sending with previous state');
}

socket.send(JSON.stringify(payload));
```

### Change 4: Reset State on New Chat (Line ~743)

Find the `newChat` function:
```javascript
function newChat() {
    welcomeScreen.classList.remove('hidden');
    messagesList.classList.add('hidden');
    messagesList.innerHTML = '';
    input.value = '';
    currentMessageId = null;
    isGenerating = false;
    autoResize(input);
}
```

Add this line before `autoResize`:
```javascript
conversationState = null;  // Reset conversation state
```

## Test After Changes

1. **Hard refresh** the page (Ctrl+Shift+R)
2. **Open browser console** (F12) to see logs
3. **Test the flow:**

```
Turn 1:
You: "I want to fill my overtime form"
[Check console: Should see "💾 Stored conversation state"]

Turn 2:
You: "Name: John Doe"
[Check console: Should see "📤 Sending with previous state"]
[System should ask for more employee info, NOT consult agents]

Turn 3:
You: "Designation: Engineer
      Department: Technical
      Grade: E4
      Month: 12
      Year: 2025"
[System should ask for OT entries]
```

## Verify It's Working

### In Browser Console:
```javascript
// After turn 1, you should see:
💾 Stored conversation state: {ot_conversation_active: true, ot_conversation_state: {...}}

// After turn 2, you should see:
📤 Sending with previous state
```

### In Backend Logs:
```
🔍 Planning: query='Name: John Doe', ot_requested=False, ot_active=True
📝 OT form detected in planning - routing to tool check (requested=False, active=True)
📝 OT form conversation: requested=False, active=True
```

## If Still Not Working

### Check WebSocket Payload in Browser DevTools:

1. Open DevTools (F12)
2. Go to **Network** tab
3. Click **WS** (WebSocket)
4. Click on the connection
5. Go to **Messages** tab
6. Check the message you're sending (turn 2):

Should look like:
```json
{
  "query": "Name: John Doe",
  "previous_state": {
    "ot_conversation_state": {...},
    "ot_conversation_active": true
  }
}
```

If `previous_state` is missing, the frontend code wasn't updated correctly.

## Complete sendMessage Function

Here's the complete function for easy copy-paste:

```javascript
function sendMessage() {
    const text = input.value.trim();
    if (!text || !isConnected || isGenerating) return;

    input.value = '';
    autoResize(input);
    welcomeScreen.classList.add('hidden');
    messagesList.classList.remove('hidden');

    // User message
    appendUserMessage(text);

    // Assistant message
    const msgId = Date.now();
    currentMessageId = msgId;
    isGenerating = true;
    appendAssistantMessage(msgId);

    // Send to server with conversation state
    const payload = { query: text };

    // Include previous state if OT conversation is active
    if (conversationState && conversationState.ot_conversation_active) {
        payload.previous_state = conversationState;
        console.log('📤 Sending with previous state:', payload.previous_state);
    }

    socket.send(JSON.stringify(payload));
}
```

---

After making these changes:
1. ✅ Hard refresh the page
2. ✅ Check browser console for logs
3. ✅ Test "I want to fill my overtime form"
4. ✅ Then test "Name: John Doe"
5. ✅ Verify it asks for more employee info instead of consulting agents

The backend is already fully configured - just need the frontend to send the state!
