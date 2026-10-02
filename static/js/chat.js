function scrollToBottom() {
  const container = document.getElementById('chatMessagesBody') || document.getElementById('chat-messages-container');
  if (container) {
    container.scrollTop = container.scrollHeight;
  }
}

// Run on page initialization
document.addEventListener('DOMContentLoaded', scrollToBottom);
