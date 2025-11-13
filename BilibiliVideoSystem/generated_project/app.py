import json
import os
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# JSON文件路径
VIDEOS_JSON_FILE = 'videos_data.json'

def load_videos_data():
    """从JSON文件加载视频数据"""
    if os.path.exists(VIDEOS_JSON_FILE):
        try:
            with open(VIDEOS_JSON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 验证数据格式
                if isinstance(data, list):
                    return data
                else:
                    app.logger.error("视频数据格式错误，期望列表但得到: %s", type(data))
                    return []
        except (json.JSONDecodeError, FileNotFoundError) as e:
            app.logger.error("加载视频数据失败: %s", str(e))
            return []
        except Exception as e:
            app.logger.error("读取视频数据文件失败: %s", str(e))
            return []
    return []

def save_videos_data(videos_data):
    """保存视频数据到JSON文件"""
    try:
        with open(VIDEOS_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(videos_data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        app.logger.error("保存视频数据失败: %s", str(e))
        return False

def validate_video_data(video_data):
    """验证视频数据完整性"""
    if not isinstance(video_data, dict):
        return False
    
    required_fields = ['title', 'bilibili_url']
    for field in required_fields:
        if field not in video_data or not video_data[field]:
            return False
    
    # 验证URL格式
    bilibili_url = video_data.get('bilibili_url', '')
    if not bilibili_url.startswith(('https://www.bilibili.com/video/', 'http://www.bilibili.com/video/')):
        return False
    
    return True

# 初始化视频数据
def init_videos_data():
    """初始化视频数据，如果文件不存在则创建默认数据"""
    if not os.path.exists(VIDEOS_JSON_FILE):
        default_videos = [
            {
                "id": 1,
                "title": "【附PDF】突然发现李飞飞的agent综述真的好清晰！！如果你agent ai很差，一定要看李飞飞整理的这份综述！！",
                "cover_color": "linear-gradient(45deg, #00a1d6, #fb7299)",
                "play_count": "2.9万",
                "danmaku_count": "45",
                "publish_date": "2025-10-24 17:29:13",
                "up_name": "AI产品经理入门教程",
                "description": "Agent入门",
                "bilibili_url": "https://www.bilibili.com/video/BV1x7sHzmEMC/"
            },
        ]
        save_videos_data(default_videos)
        return default_videos
    return load_videos_data()

@app.route('/')
def index():
    videos_data = load_videos_data()
    return render_template('index.html', videos=videos_data)

@app.route('/api/videos')
def get_videos_data():
    videos_data = load_videos_data()
    return jsonify(videos_data)

@app.route('/api/add_video', methods=['POST'])
def add_video():
    try:
        video_data = request.get_json()
        
        # 改进的数据验证
        if not video_data:
            return jsonify({"error": "请求数据为空"}), 400
        
        # 使用验证函数
        if not validate_video_data(video_data):
            return jsonify({"error": "视频数据格式不正确或缺少必要字段"}), 400
        
        # 加载现有数据
        videos_data = load_videos_data()
        
        # 检查是否已存在相同URL的视频
        existing_urls = [video.get('bilibili_url', '').lower() for video in videos_data]
        bilibili_url = video_data.get('bilibili_url', '')
        if bilibili_url.lower() in existing_urls:
            return jsonify({"error": "该视频链接已存在"}), 400
        
        # 改进的ID生成逻辑
        if videos_data:
            valid_ids = [video.get('id', 0) for video in videos_data if isinstance(video.get('id'), int)]
            new_id = max(valid_ids) + 1 if valid_ids else 1
        else:
            new_id = 1
        
        # 创建新视频对象
        new_video = {
            "id": new_id,
            "title": video_data.get('title', '').strip(),
            "cover_color": video_data.get('cover_color', 'linear-gradient(45deg, #00a1d6, #fb7299)'),
            "play_count": video_data.get('play_count', '0'),
            "danmaku_count": video_data.get('danmaku_count', '0'),
            "publish_date": video_data.get('publish_date', ''),
            "up_name": video_data.get('up_name', ''),
            "description": video_data.get('description', ''),
            "bilibili_url": bilibili_url
        }
        
        # 添加到数据并保存
        videos_data.append(new_video)
        if save_videos_data(videos_data):
            return jsonify({"message": "视频添加成功", "video": new_video})
        else:
            return jsonify({"error": "保存视频数据失败，请检查文件权限"}), 500
    
    except Exception as e:
        # 添加详细错误日志
        app.logger.error(f"添加视频失败: {str(e)}")
        return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

@app.route('/api/delete_video/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    try:
        videos_data = load_videos_data()
        original_count = len(videos_data)
        
        # 更健壮的删除逻辑
        filtered_videos = []
        video_found = False
        
        for video in videos_data:
            if video.get('id') == video_id:
                video_found = True
            else:
                filtered_videos.append(video)
        
        if not video_found:
            return jsonify({"error": "视频不存在"}), 404
            
        if save_videos_data(filtered_videos):
            return jsonify({"message": "视频删除成功"})
        else:
            return jsonify({"error": "保存数据失败"}), 500
    except Exception as e:
        app.logger.error(f"删除视频失败: {str(e)}")
        return jsonify({"error": f"服务器内部错误: {str(e)}"}), 500

# 初始化数据
init_videos_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)