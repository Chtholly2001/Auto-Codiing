class ToDoApp {
    constructor() {
        // 根据当前环境动态设置API基础URL
        this.apiBaseUrl = this.getApiBaseUrl();
        this.taskList = document.getElementById('taskList');
        this.taskInput = document.getElementById('taskInput');
        this.addTaskBtn = document.getElementById('addTaskBtn');
        this.emptyState = document.getElementById('emptyState');
        
        this.totalTasks = document.getElementById('totalTasks');
        this.completedTasks = document.getElementById('completedTasks');
        this.pendingTasks = document.getElementById('pendingTasks');

        this.init();
    }
    
    // 根据环境动态获取API基础URL
    getApiBaseUrl() {
        // 简化配置，使用相对路径
        if (window.location.port === '3000' || window.location.hostname === 'localhost') {
            // 开发环境：假设后端运行在5000端口
            return 'http://localhost:5000/api';
        }
        // 生产环境：使用同源
        return '/api';
    }
    
    init() {
        this.bindEvents();
        this.loadTasks();
        this.loadTheme(); // 加载保存的主题
    }
    
    bindEvents() {
        this.addTaskBtn.addEventListener('click', () => this.addTask());
        this.taskInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.addTask();
        });
        
        this.taskList.addEventListener('click', (e) => {
            if (e.target.classList.contains('delete-btn')) {
                const taskId = e.target.closest('.task-item').dataset.id;
                this.confirmDeleteTask(taskId);
            } else if (e.target.type === 'checkbox') {
                const taskId = e.target.closest('.task-item').dataset.id;
                const completed = e.target.checked;
                this.updateTask(taskId, { completed });
            }
        });

        // 绑定导出按钮事件
        const exportBtn = document.getElementById('exportBtn');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportTasks());
        }

        // 绑定AI总结按钮事件
        const summaryBtn = document.getElementById('summaryBtn');
        if (summaryBtn) {
            summaryBtn.addEventListener('click', () => this.generateSummary());
        }

        // 绑定搜索功能
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.searchTasks(e.target.value);
            });
        }

        // 绑定筛选功能
        const filterStatus = document.getElementById('filterStatus');
        const filterPriority = document.getElementById('filterPriority');
        if (filterStatus) {
            filterStatus.addEventListener('change', () => this.applyFilters());
        }
        if (filterPriority) {
            filterPriority.addEventListener('change', () => this.applyFilters());
        }

        // 绑定清除筛选按钮
        const clearFilters = document.getElementById('clearFilters');
        if (clearFilters) {
            clearFilters.addEventListener('click', () => {
                document.getElementById('filterStatus').value = 'all';
                document.getElementById('filterPriority').value = 'all';
                document.getElementById('searchInput').value = '';
                this.loadTasks();
            });
        }

        // 绑定主题切换按钮
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    }

    // 主题切换功能
    toggleTheme() {
        const body = document.body;
        const currentTheme = body.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        body.setAttribute('data-theme', newTheme);
        
        // 更新按钮文本
        const themeToggle = document.getElementById('themeToggle');
        themeToggle.textContent = newTheme === 'dark' ? '☀️ 切换亮色' : '🌙 切换暗色';
        
        // 保存主题偏好到本地存储
        localStorage.setItem('theme', newTheme);
    }

    // 加载保存的主题
    loadTheme() {
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.body.setAttribute('data-theme', savedTheme);
        
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.textContent = savedTheme === 'dark' ? '☀️ 切换亮色' : '🌙 切换暗色';
        }
    }
    
    async loadTasks() {
        this.showLoading(true);
        try {
            const response = await fetch(`${this.apiBaseUrl}/tasks`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const tasks = await response.json();
            this.renderTasks(tasks);
            this.updateStats(tasks);
            this.showError('', false);
        } catch (error) {
            console.error('加载任务失败:', error);
            this.showError('无法加载任务列表，请稍后重试');
        } finally {
            this.showLoading(false);
        }
    }
    
    async addTask() {
        const title = this.taskInput.value.trim();
        const priority = document.getElementById('taskPriority')?.value || 'medium';
        const dueDate = document.getElementById('taskDueDate')?.value || '';
        const tags = document.getElementById('taskTags')?.value || '';
        
        if (!title) {
            this.showError('请输入任务内容');
            return;
        }
        
        if (title.length > 100) {
            this.showError('任务内容不能超过100个字符');
            return;
        }

        // 简化前端验证，主要依赖后端验证
        if (!this.validateInput(title)) {
            this.showError('输入包含不安全字符，请重新输入');
            return;
        }

        this.showLoading(true);
        try {
            const taskData = {
                title,
                priority,
                due_date: dueDate,
                tags: tags
            };

            const response = await fetch(`${this.apiBaseUrl}/tasks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(taskData)
            });
            
            if (response.ok) {
                this.taskInput.value = '';
                await this.loadTasks();
                this.showSuccess('任务添加成功');
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = this.handleApiError(errorData, '添加任务失败，请稍后重试');
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error('添加任务失败:', error);
            this.showError(error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    async updateTask(taskId, updates) {
        this.showLoading(true);
        try {
            const response = await fetch(`${this.apiBaseUrl}/tasks/${taskId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(updates)
            });
            
            if (response.ok) {
                await this.loadTasks();
                this.showSuccess('任务更新成功');
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = this.handleApiError(errorData, '更新任务失败，请稍后重试');
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error('更新任务失败:', error);
            this.showError(error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    confirmDeleteTask(taskId) {
        const taskItem = document.querySelector(`.task-item[data-id="${taskId}"]`);
        const taskTitle = taskItem ? taskItem.querySelector('.task-title').textContent : '此任务';
        
        const modal = this.createConfirmModal(
            '确认删除',
            `确定要删除任务"${this.truncateText(taskTitle, 30)}"吗？此操作不可撤销。`,
            () => this.deleteTask(taskId)
        );
        document.body.appendChild(modal);
    }
    
    async deleteTask(taskId) {
        this.showLoading(true);
        try {
            const response = await fetch(`${this.apiBaseUrl}/tasks/${taskId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                await this.loadTasks();
                this.showSuccess('任务删除成功');
            } else {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = this.handleApiError(errorData, '删除任务失败，请稍后重试');
                throw new Error(errorMessage);
            }
        } catch (error) {
            console.error('删除任务失败:', error);
            this.showError(error.message);
        } finally {
            this.showLoading(false);
        }
    }

    // 新增：搜索任务功能
    async searchTasks(keyword) {
        if (!keyword.trim()) {
            await this.loadTasks();
            return;
        }
        
        try {
            const tasks = await this.getAllTasks();
            const filteredTasks = tasks.filter(task => 
                task.title.toLowerCase().includes(keyword.toLowerCase()) ||
                (task.tags && task.tags.toLowerCase().includes(keyword.toLowerCase()))
            );
            this.renderTasks(filteredTasks);
            this.updateStats(filteredTasks);
        } catch (error) {
            console.error('搜索任务失败:', error);
            this.showError('搜索任务失败，请稍后重试');
        }
    }

    // 新增：应用筛选功能
    async applyFilters() {
        const statusFilter = document.getElementById('filterStatus').value;
        const priorityFilter = document.getElementById('filterPriority').value;
        
        try {
            const tasks = await this.getAllTasks();
            let filteredTasks = tasks;
            
            // 状态筛选
            if (statusFilter === 'completed') {
                filteredTasks = filteredTasks.filter(task => task.completed);
            } else if (statusFilter === 'pending') {
                filteredTasks = filteredTasks.filter(task => !task.completed);
            }
            
            // 优先级筛选
            if (priorityFilter !== 'all') {
                filteredTasks = filteredTasks.filter(task => task.priority === priorityFilter);
            }
            
            this.renderTasks(filteredTasks);
            this.updateStats(filteredTasks);
        } catch (error) {
            console.error('筛选任务失败:', error);
            this.showError('筛选任务失败，请稍后重试');
        }
    }

    // 获取所有任务（用于搜索和筛选）
    async getAllTasks() {
        const response = await fetch(`${this.apiBaseUrl}/tasks`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    }

    // 新增：导出任务功能
    async exportTasks() {
        this.showLoading(true);
        try {
            const response = await fetch(`${this.apiBaseUrl}/tasks/export`);
            if (!response.ok) {
                throw new Error(`导出失败! 状态: ${response.status}`);
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;

            // 从Content-Disposition头获取文件名，或使用默认文件名
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `tasks_${new Date().toISOString().slice(0, 10)}.json`;
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }

            a.download = filename;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);

            this.showSuccess('任务导出成功');
        } catch (error) {
            console.error('导出任务失败:', error);
            this.showError('导出任务失败，请稍后重试');
        } finally {
            this.showLoading(false);
        }
    }

    // 新增：生成AI总结功能
    async generateSummary() {
        this.showLoading(true);
        try {
            const response = await fetch(`${this.apiBaseUrl}/tasks/summary`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `生成总结失败! 状态: ${response.status}`);
            }

            const result = await response.json();
            this.displaySummary(result.summary);
            this.showSuccess('AI总结生成成功');
            
        } catch (error) {
            console.error('生成AI总结失败:', error);
            this.showError(error.message || '生成AI总结失败，请稍后重试');
        } finally {
            this.showLoading(false);
        }
    }

    // 新增：显示AI总结
    displaySummary(summary) {
        let summaryContainer = document.getElementById('summaryContainer');
        if (!summaryContainer) {
            summaryContainer = document.createElement('div');
            summaryContainer.id = 'summaryContainer';
            summaryContainer.className = 'summary-container';
            document.querySelector('.container').appendChild(summaryContainer);
        }

        summaryContainer.innerHTML = `
            <div class="summary-header">
                <h3>📊 AI任务分析总结</h3>
                <button class="close-summary" id="closeSummary">×</button>
            </div>
            <div class="summary-content">
                ${summary}
            </div>
        `;

        // 绑定关闭按钮事件
        const closeBtn = document.getElementById('closeSummary');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                summaryContainer.style.display = 'none';
            });
        }

        summaryContainer.style.display = 'block';
    }

    formatDateTime(dateString) {
        if (!dateString) return '未设置';
        
        try {
            const date = new Date(dateString);
            // 使用与后端一致的时区处理
            return date.toLocaleDateString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit'
            });
        } catch (error) {
            console.error('时间格式化错误:', error);
            return dateString;
        }
    }

    getPriorityLabel(priority) {
        const priorityMap = {
            'high': '🔴 高',
            'medium': '🟡 中',
            'low': '🟢 低'
        };
        return priorityMap[priority] || '🟡 中';
    }
    
    renderTasks(tasks) {
        if (tasks.length === 0) {
            this.emptyState.style.display = 'block';
            this.taskList.innerHTML = '';
            this.taskList.appendChild(this.emptyState);
            return;
        }
        
        this.emptyState.style.display = 'none';
        this.taskList.innerHTML = tasks.map(task => `
            <div class="task-item ${task.completed ? 'completed' : ''}" data-id="${task.id}">
                <input type="checkbox" class="task-checkbox" ${task.completed ? 'checked' : ''}>
                <div class="task-content">
                    <div class="task-title">${this.escapeHtml(task.title)}</div>
                    <div class="task-meta">
                        <span class="priority-badge ${task.priority || 'medium'}">${this.getPriorityLabel(task.priority || 'medium')}</span>
                        ${task.due_date ? `<span class="due-date">截止: ${this.formatDateTime(task.due_date)}</span>` : ''}
                        ${task.tags ? `<span class="tags">标签: ${this.escapeHtml(task.tags)}</span>` : ''}
                        <span class="created-time">创建: ${this.formatDateTime(task.created_at)}</span>
                    </div>
                </div>
                <button class="delete-btn" aria-label="删除任务">删除</button>
            </div>
        `).join('');
    }
    
    updateStats(tasks) {
        const total = tasks.length;
        const completed = tasks.filter(task => task.completed).length;
        const pending = total - completed;
        
        this.totalTasks.textContent = total;
        this.completedTasks.textContent = completed;
        this.pendingTasks.textContent = pending;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    validateInput(text) {
        // 基础验证，详细验证交给后端
        if (!text || !text.trim()) return false;
        if (text.length > 100) return false;
        
        // 只检查明显的危险标签
        const dangerousTags = /<script|javascript:|on\w+\s*=/i;
        return !dangerousTags.test(text);
    }
    
    // 统一错误处理
    handleApiError(error, defaultMessage) {
        if (error && error.error) {
            return error.error;
        } else if (error && error.message) {
            return error.message;
        }
        return defaultMessage;
    }
    
    truncateText(text, maxLength) {
        if (text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }
    
    showLoading(show) {
        const existingLoader = document.getElementById('global-loader');
        if (show) {
            if (!existingLoader) {
                const loader = document.createElement('div');
                loader.id = 'global-loader';
                loader.innerHTML = `
                    <div class="loading-overlay">
                        <div class="loading-spinner"></div>
                        <div class="loading-text">加载中...</div>
                    </div>
                `;
                document.body.appendChild(loader);
            }
        } else {
            if (existingLoader) {
                existingLoader.remove();
            }
        }
    }
    
    showError(message, show = true) {
        let errorDiv = document.getElementById('error-message');
        if (!errorDiv && show) {
            errorDiv = document.createElement('div');
            errorDiv.id = 'error-message';
            errorDiv.className = 'error-message';
            document.body.insertBefore(errorDiv, document.body.firstChild);
        }
        
        if (errorDiv) {
            errorDiv.textContent = message;
            errorDiv.style.display = show ? 'block' : 'none';
            
            if (show) {
                setTimeout(() => {
                    errorDiv.style.display = 'none';
                }, 5000);
            }
        }
    }
    
    showSuccess(message) {
        let successDiv = document.getElementById('success-message');
        if (!successDiv) {
            successDiv = document.createElement('div');
            successDiv.id = 'success-message';
            successDiv.className ='success-message';
            document.body.insertBefore(successDiv, document.body.firstChild);
        }
        
        successDiv.textContent = message;}

    showSuccess(message) {
        let successDiv = document.getElementById('success-message');
        if (!successDiv) {
            successDiv = document.createElement('div');
            successDiv.id = 'success-message';
            successDiv.className ='success-message';
            document.body.insertBefore(successDiv, document.body.firstChild);
        }
        
        successDiv.textContent = message;
        successDiv.style.display = 'block';
        
        setTimeout(() => {
            successDiv.style.display = 'none';
        }, 3000);
    }
    
    createConfirmModal(title, message, onConfirm) {
        const modal = document.createElement('div');
        modal.className = 'modal-overlay';
        modal.innerHTML = `
            <div class="modal-content">
                <h3>${this.escapeHtml(title)}</h3>
                <p>${this.escapeHtml(message)}</p>
                <div class="modal-actions">
                    <button class="btn-secondary" id="modal-cancel">取消</button>
                    <button class="btn-danger" id="modal-confirm">确认删除</button>
                </div>
            </div>
        `;
        
        const cancelBtn = modal.querySelector('#modal-cancel');
        const confirmBtn = modal.querySelector('#modal-confirm');
        
        const closeModal = () => modal.remove();
        
        cancelBtn.addEventListener('click', closeModal);
        confirmBtn.addEventListener('click', () => {
            onConfirm();
            closeModal();
        });
        
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        return modal;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    new ToDoApp();
});