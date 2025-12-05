# Frontend Update Instructions for OT Form Multi-Turn Support

## Overview

To enable multi-turn OT form conversations, the frontend needs to:
1. Store the conversation state from the backend response
2. Send it back with subsequent queries

## Required Changes to [frontend/chatbotui/index.html](../frontend/chatbotui/index.html)

### Step 1: Add State Storage Variable

Add this near the top of the `<script>` section (around line 418):

```javascript
// State
let socket = null;
const WS_URL = 'ws://localhost:8082/ws/query';
let currentMessageId = null;
let isGenerating = false;
let isConnected = false;
let conversationState = null;  // ✅ NEW: Store conversation state for multi-turn
```

### Step 2: Update the `handleStreamEvent` Function

Find the `'complete'` case in `handleStreamEvent` (around line 559-562) and update it:

```javascript
case 'complete':
    finishResponse(event.data.final_answer);
    collapseThinking();
    // ✅ NEW: Store conversation state for multi-turn
    conversationState = {
        ot_conversation_state: event.data.ot_conversation_state,
        ot_conversation_active: event.data.ot_conversation_active
    };
    break;
```

### Step 3: Update the `sendMessage` Function

Find the `sendMessage()` function (around line 783-803) and update the WebSocket send:

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

    // ✅ UPDATED: Send query with conversation state
    const payload = {
        query: text
    };

    // ✅ NEW: Include previous state if exists
    if (conversationState && conversationState.ot_conversation_active) {
        payload.previous_state = conversationState;
    }

    socket.send(JSON.stringify(payload));
}
```

### Step 4: Reset State on New Chat

Update the `newChat()` function (around line 743-751) to reset conversation state:

```javascript
function newChat() {
    welcomeScreen.classList.remove('hidden');
    messagesList.classList.add('hidden');
    messagesList.innerHTML = '';
    input.value = '';
    currentMessageId = null;
    isGenerating = false;
    conversationState = null;  // ✅ NEW: Reset conversation state
    autoResize(input);
}
```

## Complete Modified Functions

Here are the complete modified functions for easy copy-paste:

### Updated handleStreamEvent (complete case only):

```javascript
case 'complete':
    finishResponse(event.data.final_answer);
    collapseThinking();
    // ✅ Store conversation state for multi-turn
    conversationState = {
        ot_conversation_state: event.data.ot_conversation_state,
        ot_conversation_active: event.data.ot_conversation_active
    };
    break;
```

### Updated sendMessage:

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

    if (conversationState && conversationState.ot_conversation_active) {
        payload.previous_state = conversationState;
    }

    socket.send(JSON.stringify(payload));
}
```

### Updated newChat:

```javascript
function newChat() {
    welcomeScreen.classList.remove('hidden');
    messagesList.classList.add('hidden');
    messagesList.innerHTML = '';
    input.value = '';
    currentMessageId = null;
    isGenerating = false;
    conversationState = null;  // Reset conversation state
    autoResize(input);
}
```

## Testing the Implementation

1. **Start the backend server:**
   ```bash
   cd multi_agent_system
   conda activate sse-ai
   python server.py
   ```

2. **Open the frontend:**
   ```
   Open frontend/chatbotui/index.html in a browser
   ```

3. **Test the OT form flow:**
   ```
   User: "I want to fill my overtime form"
   System: [Asks for employee info]

   User: "Name: John Doe, Designation: Engineer, ..."
   System: [Asks for OT entries]

   User: "Date: 2025-12-06, Start: 18:00, ..."
   System: [Records entry, asks if more needed]

   User: "done"
   System: [Shows review]

   User: "confirm"
   System: [Generates Excel file]
   ```

## Verification

To verify the implementation is working:

1. Check browser console for:
   - `conversationState` is logged when stored
   - WebSocket payload includes `previous_state` on subsequent turns

2. Check backend logs for:
   - "📝 OT form detected in planning - routing to tool check"
   - "📝 OT form conversation: requested=..." messages

3. Verify the conversation:
   - First message asks for employee info
   - Second message acknowledges info and asks for OT entries
   - Conversation maintains context across turns

## Troubleshooting

### Problem: Conversation resets after each message

**Solution**: Ensure `conversationState` is being stored in the `complete` event handler and sent with each new message.

### Problem: Backend says "OT form requested" but doesn't enter multi-turn mode

**Solution**: Check that `previous_state` is being sent in the WebSocket payload and has the correct structure.

### Problem: Frontend shows generic response instead of OT conversation

**Solution**:
1. Restart the backend server to load the updated code
2. Check that keywords like "overtime" or "ot form" are in your message
3. Verify [graph.py](graph.py) has the updated planning node code

## Optional: Session Storage Persistence

To persist conversation state across page reloads, add this:

```javascript
// After storing conversationState
conversationState = {
    ot_conversation_state: event.data.ot_conversation_state,
    ot_conversation_active: event.data.ot_conversation_active
};
// ✅ Optional: Save to sessionStorage
if (conversationState.ot_conversation_active) {
    sessionStorage.setItem('ot_conversation', JSON.stringify(conversationState));
}

// On page load, restore state
window.addEventListener('DOMContentLoaded', () => {
    const saved = sessionStorage.getItem('ot_conversation');
    if (saved) {
        conversationState = JSON.parse(saved);
        console.log('Restored OT conversation state:', conversationState);
    }
});

// Clear on new chat
function newChat() {
    // ... existing code ...
    conversationState = null;
    sessionStorage.removeItem('ot_conversation');
}
```

---

## Summary

With these changes, the frontend will:
✅ Store conversation state from backend responses
✅ Send state back with subsequent queries
✅ Enable multi-turn OT form conversations
✅ Reset state on new chat

The backend is already fully configured to handle multi-turn conversations!
