@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', sans-serif;
  background: linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%);
  min-height: 100vh;
}

.App {
  min-height: 100vh;
}

/* Custom scrollbar */
::-webkit-scrollbar {
  width: 8px;
}

::-webkit-scrollbar-track {
  background: #f1f5f9;
  border-radius: 10px;
}

::-webkit-scrollbar-thumb {
  background: linear-gradient(to bottom, #f97316, #dc2626);
  border-radius: 10px;
}

::-webkit-scrollbar-thumb:hover {
  background: linear-gradient(to bottom, #ea580c, #b91c1c);
}

/* Fix dropdown z-index issues */
[data-radix-select-content] {
  z-index: 9999 !important;
}

[data-radix-popper-content-wrapper] {
  z-index: 9999 !important;
}

.select-content {
  z-index: 9999 !important;
  position: relative;
}

/* Ensure form elements don't overlap */
.form-container {
  position: relative;
  z-index: 1;
}

.form-container > * {
  position: relative;
  z-index: 2;
}

/* Fix select trigger positioning */
.select-trigger {
  position: relative;
  z-index: 3;
}

/* Dialog content should be above everything */
[data-radix-dialog-content] {
  z-index: 10000 !important;
}

/* Card hover effects */
.card-hover {
  transition: all 0.3s ease;
  transform: translateY(0);
}

.card-hover:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0, 0, 0, 0.1);
}

/* Button animations */
button {
  transition: all 0.2s ease;
}

button:hover {
  transform: translateY(-1px);
}

button:active {
  transform: translateY(0);
}

/* Form focus states */
input:focus,
select:focus,
textarea:focus {
  box-shadow: 0 0 0 3px rgba(249, 115, 22, 0.1);
  border-color: #f97316;
}

/* Table row hover */
.table-row-hover {
  transition: background-color 0.2s ease;
}

.table-row-hover:hover {
  background-color: #fef7f0;
}

/* Badge styles */
.badge-success {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
}

.badge-warning {
  background: linear-gradient(135deg, #f59e0b, #d97706);
  color: white;
}

.badge-danger {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}

/* Loading spinner */
.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #f3f3f3;
  border-top: 2px solid #f97316;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Mobile responsiveness */
@media (max-width: 768px) {
  .container {
    padding: 1rem;
  }
  
  .grid-cols-5 {
    grid-template-columns: repeat(2, 1fr);
  }
  
  .lg\:grid-cols-3 {
    grid-template-columns: 1fr;
  }
}

/* Dashboard card animations */
.dashboard-card {
  animation: fadeInUp 0.6s ease-out;
}

.dashboard-card:nth-child(1) { animation-delay: 0.1s; }
.dashboard-card:nth-child(2) { animation-delay: 0.2s; }
.dashboard-card:nth-child(3) { animation-delay: 0.3s; }
.dashboard-card:nth-child(4) { animation-delay: 0.4s; }
.dashboard-card:nth-child(5) { animation-delay: 0.5s; }
.dashboard-card:nth-child(6) { animation-delay: 0.6s; }

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Floating elements */
.floating {
  animation: floating 3s ease-in-out infinite;
}

@keyframes floating {
  0%, 100% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
}

/* Glassmorphism effect */
.glass {
  background: rgba(255, 255, 255, 0.25);
  backdrop-filter: blur(10px);
  border: 1px solid rgba(255, 255, 255, 0.18);
}

/* Gradient text */
.gradient-text {
  background: linear-gradient(135deg, #f97316, #dc2626);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* Success message animation */
.success-message {
  animation: slideInRight 0.5s ease-out;
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(100%);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

/* Error message animation */
.error-message {
  animation: shake 0.5s ease-in-out;
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); }
  20%, 40%, 60%, 80% { transform: translateX(5px); }
}

/* Tab active state animation */
.tab-active {
  position: relative;
  overflow: hidden;
}

.tab-active::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
  animation: shine 1.5s ease-in-out;
}

@keyframes shine {
  0% { left: -100%; }
  100% { left: 100%; }
}

