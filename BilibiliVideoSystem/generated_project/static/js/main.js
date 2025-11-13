document.addEventListener('DOMContentLoaded', function() {
    console.log('B站视频预览平台已加载');
    
    // 可以在这里添加更多的交互功能
    const videoCard = document.querySelector('.video-card');
    const actionBtn = document.querySelector('.action-btn');
    
    if (videoCard) {
        videoCard.addEventListener('click', function(e) {
            if (e.target === actionBtn) {
                // 按钮点击事件已经在HTML中处理
                return;
            }
            // 可以添加卡片其他区域的点击事件
            console.log('视频卡片被点击');
        });
    }
    
    // 模拟加载动画
    const videoCover = document.querySelector('.video-cover');
    if (videoCover) {
        setTimeout(() => {
            videoCover.style.opacity = '1';
        }, 300);
    }
    
    // 添加上传表单处理功能
    const uploadForm = document.getElementById('videoUploadForm');
    const uploadStatus = document.getElementById('uploadStatus');
    
    if (uploadForm) {
        uploadForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // 获取表单数据 - 修正ID引用
            const formData = {
                title: document.getElementById('videoTitle').value,
                bilibili_url: document.getElementById('videoUrl').value,
                cover_color: document.getElementById('coverColor').value,
                play_count: document.getElementById('playCount').value || '0',
                danmaku_count: document.getElementById('danmakuCount').value || '0',
                publish_date: document.getElementById('publishDate').value,
                up_name: document.getElementById('upName').value,
                description: document.getElementById('videoDescription').value
            };
            
            // 显示上传中状态
            if (uploadStatus) {
                uploadStatus.innerHTML = '<div class="upload-status uploading">上传中...</div>';
                uploadStatus.style.display = 'block';
            }
            
            // 发送AJAX请求到后端
            fetch('/api/add_video', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(formData)
            })
            .then(response => response.json())
            .then(data => {
                if (uploadStatus) {
                    if (data.error) {
                        uploadStatus.innerHTML = `<div class="upload-status error">上传失败: ${data.error}</div>`;
                    } else {
                        uploadStatus.innerHTML = `<div class="upload-status success">上传成功！视频已添加到列表。</div>`;
                        // 清空表单
                        uploadForm.reset();
                        // 动态添加新视频到列表而不刷新页面
                        addVideoToPage(data.video);
                    }
                }
            })
            .catch(error => {
                console.error('上传错误:', error);
                if (uploadStatus) {
                    uploadStatus.innerHTML = `<div class="upload-status error">网络错误，请重试</div>`;
                }
            });
        });
    }
    
    // 添加上传表单验证
    const videoUrlInput = document.getElementById('videoUrl');
    if (videoUrlInput) {
        videoUrlInput.addEventListener('blur', function() {
            const url = this.value;
            if (uploadStatus) {
                videoUrlInput.style.borderColor = '';
                uploadStatus.style.display = 'none';
            }
        });
    }
    
    // 动态添加视频到页面的函数
    function addVideoToPage(videoData) {
        const videosGrid = document.querySelector('.videos-grid');
        if (!videosGrid) return;
        
        const videoCard = document.createElement('div');
        videoCard.className = 'video-card';
        videoCard.setAttribute('data-video-id', videoData.id);
        videoCard.innerHTML = `
            <div class="video-cover-container">
                <div class="video-cover" style="background: ${videoData.cover_color || 'linear-gradient(45deg, #00a1d6, #fb7299)'};"></div>
                <div class="video-overlay">
                    <a href="${videoData.bilibili_url || '#'}" class="play-link" target="_blank">
                        <span class="play-icon">▶</span>
                    </a>
                </div>
            </div>
            <div class="video-content">
                <h3 class="video-title">${videoData.title || '未命名视频'}</h3>
                <div class="video-meta">
                    <div class="meta-item">
                        <span class="meta-icon">👁️</span>
                        <span>${videoData.play_count || '0'}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-icon">💬</span>
                        <span>${videoData.danmaku_count || '0'}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-icon">📅</span>
                        <span>${videoData.publish_date || '未知日期'}</span>
                    </div>
                </div>
                <div class="up-info">
                    <div class="up-avatar">
                        <span class="avatar-text">UP</span>
                    </div>
                    <div class="up-details">
                        <div class="up-name">${videoData.up_name || '未知UP主'}</div>
                        <div class="up-badge">UP主</div>
                    </div>
                </div>
                <p class="video-desc">${videoData.description || '暂无描述'}</p>
                <div class="video-actions">
                    <a href="${videoData.bilibili_url || '#'}" class="watch-btn" target="_blank">
                        <span class="btn-icon">▶</span>
                        前往B站观看完整视频
                    </a>
                    <button class="delete-btn" onclick="deleteVideo(${videoData.id})" data-video-id="${videoData.id}">
                        <span class="btn-icon">🗑️</span>
                        删除
                    </button>
                </div>
            </div>
        `;
        
        // 添加到网格的开头
        videosGrid.insertBefore(videoCard, videosGrid.firstChild);
        
        // 添加动画效果
        setTimeout(() => {
            videoCard.style.opacity = '1';
            videoCard.style.transform = 'translateY(0)';
        }, 10);
    }
});

// 删除视频函数
function deleteVideo(videoId) {
    if (confirm('确定要删除这个视频吗？')) {
        fetch(`/api/delete_video/${videoId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert('删除失败: ' + data.error);
            } else {
                // 从页面移除视频卡片
                const videoCard = document.querySelector(`[data-video-id="${videoId}"]`).closest('.video-card');
                if (videoCard) {
                    videoCard.remove();
                }
                alert('视频删除成功');
            }
        })
        .catch(error => {
            alert('网络错误: ' + error.message);
        });
    }
}