var ws = new WebSocket("ws://localhost:8000/ws");

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);  // parse JSON

    const messages = document.getElementById('messages');
    const messageItem = document.createElement('li');

    

    // Timestamp
    const timestamp = new Date(data.timestamp);
    const formatted = timestamp.toLocaleString('en-GB', {
        day: 'numeric', month: 'long', year: 'numeric',
        hour: '2-digit', minute: '2-digit',
        hour12: true
    });

    const timeEl = document.createElement('time');
    timeEl.setAttribute('datetime', timestamp.toISOString());
    timeEl.setAttribute('aria-label', formatted);
    timeEl.textContent = formatted.replace(',', '');
    


    const textNode = document.createElement('span');
    textNode.innerHTML = `<strong>${data.user || "anon"}</strong>: ${data.text}`;

    
    messageItem.appendChild(textNode);
    messageItem.appendChild(timeEl);
    messages.appendChild(messageItem);
};

function sendMessage(event) {
    var input = document.getElementById("messageText");
    
    ws.send(JSON.stringify({ text: input.value, user:username }));
    input.value = '';
    event.preventDefault();
}
