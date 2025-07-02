// Learning Module Application Logic
class LearningModule {
    constructor() {
        this.currentSlide = 1;
        this.totalSlides = 6;
        this.slideData = {
            dragDropItems: [
                {id: "excel", text: "Excel Spreadsheet", category: "structured", explanation: "Excel files organize data in rows and columns with defined structure"},
                {id: "email", text: "Email Message", category: "unstructured", explanation: "Emails contain free-form text without predefined structure"},
                {id: "video", text: "Video File", category: "unstructured", explanation: "Videos are multimedia content without tabular structure"},
                {id: "csv", text: "CSV File", category: "structured", explanation: "CSV files organize data in comma-separated rows and columns"},
                {id: "pdf", text: "PDF Document", category: "unstructured", explanation: "PDFs can contain various content types without consistent structure"},
                {id: "OASIS", text: "OASIS Export", category: "structured", explanation: "Data in OASIS is highly structured so that different functions can be performed with the data"},
                {id: "social", text: "Social Media Post", category: "unstructured", explanation: "Social media posts are free-form content without predetermined format"},
                {id: "word", text: "Word Document", category: "unstructured", explanation: "Word documents contain formatted text without tabular structure"},
                {id: "smartsheet", text: "SmartSheet", category: "structured", explanation: "Smartsheets, just like excel, have a tabular structure"}
    
            ],
            dataTypeQuiz: [
                {question: "\"UCD38928\"", correct: "string", explanation: "OASIS usernames contain letters and numbers, but are still strings"},
                {question: "42", correct: "integer", explanation: "Whole numbers are integer data types.  If you use OASIS, you will see this in split IDs and serial IDs."},
                {question: "3.14159", correct: "float", explanation: "Numbers with decimal points are float data types"},
                {question: "true", correct: "boolean", explanation: "True/false values are boolean data types"},
                {question: "2024-07-03", correct: "datetime", explanation: "Date representations are datetime data types"},
                {question: "\"1230489_Kedl_Ben_AMC\"", correct: "string", explanation: "Oasis Groups are strings, even though they contain numbers and symbols."},
                {question: "-17", correct: "integer", explanation: "Negative whole numbers are still integer data types"},
                {question: "93.5", correct: "float", explanation: "Decimal numbers, like grades, are float data types"},
                {question: "\"2024\"", correct: "string", explanation: "Numbers in quotes are treated as string data type"},
                {question: "12:30:45", correct: "datetime", explanation: "Time representations are datetime data types"}
            ]
        };

        // Initialize exercise state
        this.dragDropState = {
            score: 0,
            totalAttempts: 0,
            completedItems: new Set()
        };

        this.quizState = {
            currentQuestion: 0,
            score: 0,
            totalAnswered: 0,
            questions: [...this.slideData.dataTypeQuiz]
        };

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.initializeDragDrop();
        this.initializeQuiz();
        this.updateProgress();
        this.updateNavigation();
    }

    setupEventListeners() {
        // Navigation
        document.getElementById('prevButton').addEventListener('click', () => this.previousSlide());
        document.getElementById('nextButton').addEventListener('click', () => this.nextSlide());

        // Drag and drop reset
        document.getElementById('resetButton').addEventListener('click', () => this.resetDragDrop());

        // Quiz reset and navigation
        document.getElementById('resetQuizButton').addEventListener('click', () => this.resetQuiz());
        document.getElementById('nextQuestionButton').addEventListener('click', () => this.nextQuestion());
    }
   

    initializeDragDrop() {
        const itemsGrid = document.getElementById('itemsGrid');
        const structuredZone = document.getElementById('structuredZone');
        const unstructuredZone = document.getElementById('unstructuredZone');

        // Create draggable items
        this.slideData.dragDropItems.forEach(item => {
            const itemElement = document.createElement('div');
            itemElement.className = 'draggable-item';
            itemElement.draggable = true;
            itemElement.dataset.id = item.id;
            itemElement.dataset.category = item.category;
            itemElement.textContent = item.text;
            
            itemElement.addEventListener('dragstart', this.handleDragStart.bind(this));
            itemElement.addEventListener('dragend', this.handleDragEnd.bind(this));
            
            itemsGrid.appendChild(itemElement);
        });

        // Setup drop zones
        [structuredZone, unstructuredZone].forEach(zone => {
            zone.addEventListener('dragover', this.handleDragOver.bind(this));
            zone.addEventListener('drop', this.handleDrop.bind(this));
            zone.addEventListener('dragenter', this.handleDragEnter.bind(this));
            zone.addEventListener('dragleave', this.handleDragLeave.bind(this));
        });

        this.updateDragDropScore();
    }

    handleDragStart(e) {
        e.dataTransfer.setData('text/plain', e.target.dataset.id);
        e.target.classList.add('dragging');
    }

    handleDragEnd(e) {
        e.target.classList.remove('dragging');
    }

    handleDragOver(e) {
        e.preventDefault();
    }

    handleDragEnter(e) {
        e.preventDefault();
        if (e.target.classList.contains('drop-zone')) {
            e.target.classList.add('drag-over');
        }
    }

    handleDragLeave(e) {
        if (e.target.classList.contains('drop-zone')) {
            e.target.classList.remove('drag-over');
        }
    }

    handleDrop(e) {
        e.preventDefault();
        const itemId = e.dataTransfer.getData('text/plain');
        const item = this.slideData.dragDropItems.find(i => i.id === itemId);
        const dropZone = e.target.closest('.drop-zone');
        
        if (!dropZone || !item) return;

        dropZone.classList.remove('drag-over');
        
        const draggedElement = document.querySelector(`[data-id="${itemId}"]`);
        const dropZoneCategory = dropZone.id === 'structuredZone' ? 'structured' : 'unstructured';
        const isCorrect = item.category === dropZoneCategory;
        
        // Update visual feedback
        draggedElement.classList.remove('correct', 'incorrect');
        draggedElement.classList.add(isCorrect ? 'correct' : 'incorrect');
        
        // Move to drop zone
        const droppedItems = dropZone.querySelector('.dropped-items');
        droppedItems.appendChild(draggedElement);
        
        // Update score
        this.dragDropState.totalAttempts++;
        if (isCorrect) {
            this.dragDropState.score++;
        }
        this.dragDropState.completedItems.add(itemId);
        
        this.updateDragDropScore();
        this.showDragDropFeedback(item, isCorrect);
        
        // Check if all items are completed
        if (this.dragDropState.completedItems.size === this.slideData.dragDropItems.length) {
            this.showDragDropCompletion();
        }
    }

    updateDragDropScore() {
        const scoreText = document.getElementById('scoreText');
        scoreText.textContent = `Score: ${this.dragDropState.score}/${this.dragDropState.totalAttempts}`;
    }

    showDragDropFeedback(item, isCorrect) {
        const feedbackSection = document.getElementById('feedbackSection');
        const feedbackItem = document.createElement('div');
        feedbackItem.className = `feedback-item ${isCorrect ? 'correct' : 'incorrect'}`;
        
        feedbackItem.innerHTML = `
            <span class="feedback-icon">${isCorrect ? '✓' : '✗'}</span>
            <div>
                <strong>${item.text}:</strong> ${item.explanation}
            </div>
        `;
        
        feedbackSection.appendChild(feedbackItem);
        feedbackItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    showDragDropCompletion() {
        const feedbackSection = document.getElementById('feedbackSection');
        const completionMessage = document.createElement('div');
        completionMessage.className = 'feedback-item correct';
        completionMessage.innerHTML = `
            <span class="feedback-icon">🎉</span>
            <div>
                <strong>Exercise Complete!</strong> You've categorized all items. 
                Final Score: ${this.dragDropState.score}/${this.dragDropState.totalAttempts}
                ${this.dragDropState.score === this.dragDropState.totalAttempts ? ' - Perfect!' : ''}
            </div>
        `;
        feedbackSection.appendChild(completionMessage);
    }

    resetDragDrop() {
        // Reset state
        this.dragDropState = {
            score: 0,
            totalAttempts: 0,
            completedItems: new Set()
        };
        
        // Move all items back to original grid
        const itemsGrid = document.getElementById('itemsGrid');
        const allItems = document.querySelectorAll('.draggable-item');
        
        allItems.forEach(item => {
            item.classList.remove('correct', 'incorrect');
            itemsGrid.appendChild(item);
        });
        
        // Clear feedback
        document.getElementById('feedbackSection').innerHTML = '';
        
        this.updateDragDropScore();
    }

    initializeQuiz() {
        this.shuffleArray(this.quizState.questions);
        this.displayCurrentQuestion();
        this.setupQuizEventListeners();
        this.updateQuizScore();
    }

    setupQuizEventListeners() {
        const options = document.querySelectorAll('.quiz-option');
        options.forEach(option => {
            option.addEventListener('click', (e) => this.handleQuizAnswer(e.target.dataset.type));
        });
    }

    displayCurrentQuestion() {
        const valueDisplay = document.getElementById('valueDisplay');
        const questionCounter = document.getElementById('questionCounter');
        const nextButton = document.getElementById('nextQuestionButton');
        const feedback = document.getElementById('quizFeedback');
        
        if (this.quizState.currentQuestion >= this.quizState.questions.length) {
            this.showQuizCompletion();
            return;
        }
        
        const currentQ = this.quizState.questions[this.quizState.currentQuestion];
        valueDisplay.textContent = currentQ.question;
        questionCounter.textContent = `Question ${this.quizState.currentQuestion + 1} of ${this.quizState.questions.length}`;
        
        // Reset options
        const options = document.querySelectorAll('.quiz-option');
        options.forEach(option => {
            option.classList.remove('correct', 'incorrect');
            option.disabled = false;
        });
        
        // Clear feedback
        feedback.textContent = '';
        feedback.className = 'quiz-feedback';
        nextButton.style.display = 'none';
    }

    handleQuizAnswer(selectedType) {
        const currentQ = this.quizState.questions[this.quizState.currentQuestion];
        const isCorrect = selectedType === currentQ.correct;
        const feedback = document.getElementById('quizFeedback');
        const nextButton = document.getElementById('nextQuestionButton');
        const options = document.querySelectorAll('.quiz-option');
        
        // Disable all options
        options.forEach(option => {
            option.disabled = true;
            if (option.dataset.type === currentQ.correct) {
                option.classList.add('correct');
            } else if (option.dataset.type === selectedType && !isCorrect) {
                option.classList.add('incorrect');
            }
        });
        
        // Show feedback
        feedback.className = `quiz-feedback ${isCorrect ? 'correct' : 'incorrect'}`;
        feedback.textContent = currentQ.explanation;
        
        // Update score
        this.quizState.totalAnswered++;
        if (isCorrect) {
            this.quizState.score++;
        }
        
        this.updateQuizScore();
        
        // Show next button
        nextButton.style.display = 'block';
    }

    nextQuestion() {
        this.quizState.currentQuestion++;
        this.displayCurrentQuestion();
    }

    updateQuizScore() {
        const scoreText = document.getElementById('quizScoreText');
        scoreText.textContent = `Score: ${this.quizState.score}/${this.quizState.totalAnswered}`;
    }

    showQuizCompletion() {
        const valueDisplay = document.getElementById('valueDisplay');
        const questionCounter = document.getElementById('questionCounter');
        const answerOptions = document.querySelector('.answer-options');
        const feedback = document.getElementById('quizFeedback');
        const nextButton = document.getElementById('nextQuestionButton');
        
        valueDisplay.textContent = 'Quiz Complete!';
        questionCounter.textContent = 'All questions answered';
        answerOptions.style.display = 'none';
        nextButton.style.display = 'none';
        
        const percentage = Math.round((this.quizState.score / this.quizState.totalAnswered) * 100);
        feedback.className = 'quiz-feedback correct';
        feedback.innerHTML = `
            🎉 <strong>Quiz Complete!</strong><br>
            Final Score: ${this.quizState.score}/${this.quizState.totalAnswered} (${percentage}%)<br>
            ${percentage >= 80 ? 'Excellent work!' : percentage >= 60 ? 'Good job!' : 'Keep practicing!'}
        `;
    }

    resetQuiz() {
        this.quizState = {
            currentQuestion: 0,
            score: 0,
            totalAnswered: 0,
            questions: [...this.slideData.dataTypeQuiz]
        };
        
        this.shuffleArray(this.quizState.questions);
        document.querySelector('.answer-options').style.display = 'grid';
        this.displayCurrentQuestion();
        this.updateQuizScore();
    }

    shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
    }

    previousSlide() {
        if (this.currentSlide > 1) {
            this.currentSlide--;
            this.updateSlideDisplay();
             window.scrollTo({
                top: 0,
                left: 0,
                behavior: 'instant' // Ensures it jumps instantly
            });
            this.updateProgress();
            this.updateNavigation();
        }
    }

    nextSlide() {
        if (this.currentSlide < this.totalSlides) {
            this.currentSlide++;
            this.updateSlideDisplay();
              window.scrollTo({
                top: 0,
                left: 0,
                behavior: 'instant' // Ensures it jumps instantly
            });
            this.updateProgress();
            this.updateNavigation();
        }
    }

    updateSlideDisplay() {
        const slides = document.querySelectorAll('.slide');
        slides.forEach((slide, index) => {
            slide.classList.remove('active', 'prev');
            if (index + 1 === this.currentSlide) {
                slide.classList.add('active');
            } else if (index + 1 < this.currentSlide) {
                slide.classList.add('prev');
            }
        });
    }

    updateProgress() {
        const progressFill = document.getElementById('progressFill');
        const progressText = document.getElementById('progressText');
        
        const percentage = (this.currentSlide / this.totalSlides) * 100;
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = `${this.currentSlide} of ${this.totalSlides}`;
    }

    updateNavigation() {
        const prevButton = document.getElementById('prevButton');
        const nextButton = document.getElementById('nextButton');
        
        prevButton.disabled = this.currentSlide === 1;
        nextButton.disabled = this.currentSlide === this.totalSlides;
        
        if (this.currentSlide === this.totalSlides) {
            nextButton.textContent = 'Completed';
        } else {
            nextButton.textContent = 'Next';
        }
    }
}

// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new LearningModule();
});