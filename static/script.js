
document.addEventListener('DOMContentLoaded', () => {
    const sendBtn = document.getElementById('send-btn');
    const userInput = document.getElementById('user-input');
    const messages = document.getElementById('messages');
    
    // Add a flag to ensure the intro message is displayed only once
    let introDisplayed = false;

    // Display the introductory message
    function displayIntroMessage() {
        if (!introDisplayed) {
            appendMessage(
                `Hi I am MediGuide. 
                 I can help you in predicting your disease based on your symptoms. Please provide your symptoms.`,
                'bot'
            );
            introDisplayed = true; // Mark the intro message as displayed
        }
    }

    // Call the intro message function once on load
    displayIntroMessage();
    
    // Define the sequence of detail prompts
    const detailPrompts = [
        { key: 'description', question: 'Do you want to see the description of this disease?' },
        { key: 'precautions', question: 'Do you want to see the precautions for this disease?' },
        { key: 'medications', question: 'Do you want to see the recommended medications?' },
        { key: 'diet', question: 'Do you want to see the suggested diet?' },
        { key: 'workout', question: 'Do you want to see some suggestions?' }
    ];

     // State variables
     let conversationState = 'awaiting_symptoms'; // Other states: 'awaiting_detail_confirmation', 'awaiting_new_prediction', 'completed'
     let currentDisease = '';
     let diseaseDetails = {};
     let currentPromptIndex = 0;
     let currentChatId = null;
    
    // Event listener for the Send button
    sendBtn.addEventListener('click', () => {
        const input = userInput.value.trim();
        if (input === '') return;

        appendMessage(input, 'user');
        userInput.value = '';

        if (conversationState === 'awaiting_symptoms') {
            predictDisease(input);
        } else if (conversationState === 'awaiting_detail_confirmation') {
            handleDetailResponse(input.toLowerCase());
        } else if (conversationState === 'awaiting_new_prediction') {
            handleNewPredictionResponse(input.toLowerCase());
        }
    });

    // Event listener for the Enter key
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendBtn.click();
        }
    });



    // Function to append messages to the chatbox
    function appendMessage(message, sender) {
        const msgDiv = document.createElement('div');
        msgDiv.classList.add('message');
        msgDiv.classList.add(sender === 'user' ? 'user-message' : 'bot-message');
        const avatar = document.createElement('img');
        avatar.classList.add('avatar');
        avatar.src = sender === 'user' ? 'static/images/avatar.png' : 'static/images/chatbot-avatar.jpg';
        avatar.alt = sender === 'user' ? 'User Avatar' : 'Bot Avatar';

        const textDiv = document.createElement('div');
        textDiv.classList.add('message-bubble');
        textDiv.innerHTML = marked.parse(message); // Render Markdown

        if (sender === 'user') {
            msgDiv.appendChild(textDiv);
            msgDiv.appendChild(avatar); // User avatar on the right
        } else {
            msgDiv.appendChild(avatar); // Bot avatar on the left
            msgDiv.appendChild(textDiv);
        }

        messages.appendChild(msgDiv);
        messages.scrollTop = messages.scrollHeight;
    }

    

    // Function to predict disease based on symptoms
    async function predictDisease(symptoms) {
        // Split the symptoms by comma, trim spaces, remove empty entries
        const symptomsList = [...new Set(symptoms.split(',').map(s => s.trim().toLowerCase()).filter(s => s !== ''))];

        // Frontend Validation: Check if at least 3 symptoms are provided
        if (symptomsList.length < 3) {
            appendMessage('Please enter at least **three** symptoms separated by commas.', 'bot');
            return; // Do not proceed with the prediction
        }

        appendMessage('Processing your symptoms...', 'bot');

        // Show typing indicator
        appendMessage('Bot is typing...', 'bot');

        try {
            // Send symptoms to backend for prediction
            const response = await fetch('/predict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ symptoms: symptomsList }),
            });

            const data = await response.json();

            // Remove typing indicator
            removeLastBotMessage();

            if (response.ok) {
                const disease = data.disease;
                currentDisease = disease;
                currentChatId = data.chat_id;
                appendMessage(`**Predicted Disease:** ${disease}`, 'bot');
                fetchDetails(disease);
            } else {
                // Display backend error message
                appendMessage(`**Error:** ${data.error}`, 'bot');
            }
        } catch (error) {
            // Remove typing indicator
            removeLastBotMessage();

            appendMessage('An error occurred while predicting the disease.', 'bot');
            console.error(error);
        }
    }

    // Function to fetch disease details
    async function fetchDetails(disease) {
        appendMessage('Fetching disease details...', 'bot');

        try {
            const response = await fetch('/details', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ disease, chat_id: currentChatId }),
            });

            const data = await response.json();

            if (response.ok) {
                diseaseDetails = data;
                // Start the detail confirmation process
                conversationState = 'awaiting_detail_confirmation';
                currentPromptIndex = 0;
                askNextDetail();
            } else {
                appendMessage(`**Error:** ${data.error}`, 'bot');
            }
        } catch (error) {
            appendMessage('An error occurred while fetching disease details.', 'bot');
            console.error(error);
        }
    }

    // Function to ask the next detail prompt
    function askNextDetail() {
        if (currentPromptIndex < detailPrompts.length) {
            const prompt = detailPrompts[currentPromptIndex].question;
            appendMessage(prompt, 'bot');
        } else {
            appendMessage('Thank you for using the Disease Prediction Chatbot!', 'bot');
            appendMessage('Would you like to start a new prediction? (yes/no)', 'bot');
            conversationState = 'awaiting_new_prediction';
        }
    }

    // Function to handle user's response to detail prompts
    function handleDetailResponse(response) {
        const promptObj = detailPrompts[currentPromptIndex];
        if (!promptObj) {
            appendMessage('Unexpected state. Please start over.', 'bot');
            conversationState = 'awaiting_symptoms';
            return;
        }

        if (response === 'yes' || response === 'y') {
            const detailKey = promptObj.key;
            displayDetail(detailKey);
            // Send the detail key to the backend to record it
            recordDetailViewed(detailKey);
        } else if (response === 'no' || response === 'n') {
            // Do nothing, just move to the next prompt
        } else {
            appendMessage("Please answer with 'yes' or 'no'.", 'bot');
            return; // Ask the same question again
        }

        currentPromptIndex++;
        askNextDetail();
    }

    // Function to handle user's response to new prediction prompt
    function handleNewPredictionResponse(response) {
        if (response === 'yes' || response === 'y') {
            appendMessage('Great! Please enter your symptoms separated by commas.', 'bot');
            conversationState = 'awaiting_symptoms';
        } else if (response === 'no' || response === 'n') {
            appendMessage('Goodbye! Stay healthy!', 'bot');
            conversationState = 'completed';
        } else {
            appendMessage("Please answer with 'yes' or 'no'.", 'bot');
        }
    }

    // Function to display the requested detail
    function displayDetail(detailKey) {
        switch (detailKey) {
            case 'description':
                appendMessage(`**Description:** ${diseaseDetails.description}`, 'bot');
                break;
            case 'precautions':
                const precautionsList = diseaseDetails.precautions.map(p => `- ${p}`).join('<br>');
                appendMessage(`**Precautions:**<br>${precautionsList}`, 'bot');
                break;
            case 'medications':
                const medicationsList = diseaseDetails.medications.map(m => `- ${m}`).join('<br>');
                appendMessage(`**Medications:**<br>${medicationsList}`, 'bot');
                break;
            case 'diet':
                const dietList = diseaseDetails.diet.map(d => `- ${d}`).join('<br>');
                appendMessage(`**Diet:**<br>${dietList}`, 'bot');
                break;
            case 'workout':
                appendMessage(`**Recommendations:** ${diseaseDetails.workout}`, 'bot');
                break;
            default:
                appendMessage('No details available.', 'bot');
        }
    }

    // Function to record which details the user has viewed
    async function recordDetailViewed(detailKey) {
        try {
            await fetch('/details', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ disease: currentDisease, chat_id: currentChatId, detail_key: detailKey }),
            });
        } catch (error) {
            console.error('Error recording detail viewed:', error);
        }
    }

    // Function to remove the last bot message (used for typing indicator)
    function removeLastBotMessage() {
        const messagesDiv = document.getElementById('messages');
        const lastMessage = messagesDiv.lastChild;
        if (lastMessage && lastMessage.classList.contains('bot-message') && lastMessage.innerHTML.trim() === '<p>Bot is typing...</p>') {
            messagesDiv.removeChild(lastMessage);
        }
    }

});
