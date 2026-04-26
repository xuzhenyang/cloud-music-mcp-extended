#!/usr/bin/env python3
import os
import sys
import logging

# 彻底静音：将 stderr 重定向到 devnull
# 这样可以消除 FastMCP 的 Banner 以及所有第三方库的日志干扰
sys.stderr = open(os.devnull, "w")

# 在导入 FastMCP 之前设置环境变量以抑制日志和 Banner
os.environ["LOGURU_LEVEL"] = "WARNING"
os.environ["CI"] = "true"

from fastmcp import FastMCP
import subprocess
import json
import base64

# 确保能导入同级模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from cloud_music_mcp.log import setup_logging
from cloud_music_mcp.auth import check_login_status, login_via_qrcode
from cloud_music_mcp.api import (
    get_daily_recommendations,
    get_user_playlists,
    search_song,
    get_song_detail,
    get_audio_url,
    get_artist_tracks,
    get_album_songs,
    create_playlist,
    add_tracks_to_playlist,
    get_similar_songs,
    get_similar_artists,
)

# 配置日志 (初始化)
logger = setup_logging("main")

# 抑制 FastMCP 和相关库的日志
logging.getLogger("fastmcp").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

# 抑制 pyncm 的日志输出，防止溢出到 LLM client
logging.getLogger("pyncm").setLevel(logging.WARNING)
logging.getLogger("pyncm.api").setLevel(logging.WARNING)
logging.getLogger("pyncm.helper").setLevel(logging.WARNING)

# 初始化 MCP Server
mcp = FastMCP("Cloud-Music-MCP")


@mcp.tool()
def cloud_music_status():
    """检查网易云音乐当前是否已登录"""
    logger.info("Calling cloud_music_status")
    status = check_login_status()
    if status["logged_in"]:
        return f"已登录，当前用户: {status['nickname']}"
    else:
        return "未登录，请使用 cloud_music_login 进行扫码登录"


@mcp.tool()
def cloud_music_login():
    """
    登录网易云音乐 (模拟 OAuth 流程)
    调用此工具后，电脑会弹出一张二维码图片。
    请用网易云音乐 App 扫描该二维码。
    扫描成功后，工具会自动保存登录状态。
    """
    logger.info("Calling cloud_music_login")
    return login_via_qrcode()


@mcp.tool()
def cloud_music_get_daily_recommend():
    """
    获取今日推荐歌曲
    返回歌曲列表 (包含 ID, 歌名, 歌手)
    """
    logger.info("Calling cloud_music_get_daily_recommend")
    result = get_daily_recommendations()
    if result["success"]:
        # 格式化输出以便阅读
        text = f"📅 今日推荐 ({len(result['songs'])}首):\n"
        for i, song in enumerate(result["songs"][:10], 1):  # 只展示前10首
            text += f"{i}. {song['name']} - {song['artist']} (ID: {song['id']})\n"
        return text
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_my_playlists():
    """
    获取我的歌单 (包括创建的歌单和红心歌单)
    """
    logger.info("Calling cloud_music_my_playlists")
    result = get_user_playlists()
    if result["success"]:
        text = "我的歌单:\n"
        for pl in result["playlists"]:
            mark = (
                "❤️ " if "喜欢" in pl["name"] else ("👤 " if pl["is_mine"] else "收藏 ")
            )
            text += f"{mark} {pl['name']} (ID: {pl['id']}, {pl['count']}首)\n"
        return text
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_search(keyword: str):
    """
    搜索歌曲
    args:
        keyword: 歌名或歌手
    """
    logger.info(f"Calling cloud_music_search with keyword: {keyword}")
    result = search_song(keyword)
    if result["success"]:
        return result["songs"]
    else:
        return f"搜索失败: {result.get('error')}"


@mcp.tool()
def cloud_music_play(id: str, type: str = "song"):
    """
    唤起客户端播放指定歌曲或歌单
    args:
        id: 歌曲ID 或 歌单ID
        type: 'song' (单曲) 或 'playlist' (歌单)
    """
    logger.info(f"Calling cloud_music_play with id: {id}, type: {type}")
    try:
        # 构造 JSON 指令
        command = {"type": type, "id": str(id), "cmd": "play"}

        # 序列化并 Base64 编码
        json_str = json.dumps(command, separators=(",", ":"))
        encoded = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")

        # 生成客户端 URL Scheme
        app_url = f"orpheus://{encoded}"
        logger.info(f"Generated App URL: {app_url}")

        # 尝试唤起客户端
        try:
            if sys.platform == "win32":
                os.startfile(app_url)
            else:
                # macOS open 命令，检查返回码
                ret = subprocess.run(["open", app_url], capture_output=True)
                if ret.returncode != 0:
                    raise FileNotFoundError("macOS open failed")

            return f"已发送播放指令: {type} {id}"

        except (OSError, FileNotFoundError, subprocess.CalledProcessError) as e:
            logger.warning(f"无法唤起客户端: {e}，尝试使用网页版")

            # 构造网页版 URL
            # 单曲: https://music.163.com/#/song?id=123
            # 歌单: https://music.163.com/#/playlist?id=123
            web_type = "song" if type == "song" else "playlist"
            web_url = f"https://music.163.com/#/{web_type}?id={id}"

            if sys.platform == "win32":
                os.startfile(web_url)
            else:
                subprocess.run(["open", web_url])

            return f"⚠️ 未检测到客户端，已在浏览器中播放: {web_url}"

    except Exception as e:
        logger.error(f"播放失败: {e}")
        return f"播放失败: {e}"


@mcp.tool()
def cloud_music_create_playlist(name: str, privacy: bool = False):
    """
    创建网易云歌单
    args:
        name: 歌单名称
        privacy: 是否设为隐私歌单 (默认 False)
    """
    logger.info(f"Calling cloud_music_create_playlist: {name}")
    result = create_playlist(name, privacy)
    if result["success"]:
        return f"✅ 歌单创建成功: '{name}' (ID: {result['playlist_id']})"
    else:
        return f"创建失败: {result.get('error')}"


@mcp.tool()
def cloud_music_add_tracks(playlist_id: str, track_ids: list):
    """
    批量添加歌曲到歌单
    args:
        playlist_id: 歌单 ID
        track_ids: 歌曲 ID 列表，例如 ["12345", "67890"]
    """
    logger.info(f"Calling cloud_music_add_tracks: playlist={playlist_id}, tracks={track_ids}")
    result = add_tracks_to_playlist(playlist_id, track_ids)
    if result["success"]:
        return f"✅ 已添加 {len(track_ids)} 首歌曲到歌单 (ID: {playlist_id})"
    else:
        return f"添加失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_song_detail(song_id: str):
    """
    获取歌曲详情
    args:
        song_id: 歌曲 ID (网易云)
    """
    logger.info(f"Calling cloud_music_get_song_detail: song={song_id}")
    result = get_song_detail(song_id)
    if result["success"]:
        return {
            "id": result["id"],
            "name": result["name"],
            "artist": result["artist"],
            "artist_id": result.get("artist_id"),
            "album": result["album"],
            "album_id": result.get("album_id"),
        }
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_audio_url(song_id: str):
    """
    获取歌曲音频下载链接
    args:
        song_id: 歌曲 ID (网易云)
    """
    logger.info(f"Calling cloud_music_get_audio_url: song={song_id}")
    result = get_audio_url(song_id)
    if result["success"]:
        return {
            "id": result["id"],
            "url": result["url"],
            "br": result["br"],
            "type": result["type"],
            "duration": result["duration"],
        }
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_artist_tracks(artist_id: str, limit: int = 30):
    """
    获取艺术家的热门歌曲
    args:
        artist_id: 艺术家 ID (网易云)
        limit: 返回数量 (默认 30)
    """
    logger.info(f"Calling cloud_music_get_artist_tracks: artist={artist_id}, limit={limit}")
    result = get_artist_tracks(artist_id, limit)
    if result["success"]:
        return result["songs"]
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_album_songs(album_id: str):
    """
    获取专辑的歌曲列表
    args:
        album_id: 专辑 ID (网易云)
    """
    logger.info(f"Calling cloud_music_get_album_songs: album={album_id}")
    result = get_album_songs(album_id)
    if result["success"]:
        return result["songs"]
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_similar_songs(song_id: str, limit: int = 20):
    """
    获取与指定歌曲相似的歌
    args:
        song_id: 歌曲 ID (网易云)
        limit: 返回数量 (默认 20)
    """
    logger.info(f"Calling cloud_music_get_similar_songs: song={song_id}, limit={limit}")
    result = get_similar_songs(song_id, limit)
    if result["success"]:
        text = f"🔍 相似推荐 ({len(result['songs'])}首):\n"
        for i, song in enumerate(result["songs"], 1):
            text += f"{i}. {song['name']} - {song['artist']} (ID: {song['id']})\n"
        return text
    else:
        return f"获取失败: {result.get('error')}"


@mcp.tool()
def cloud_music_get_similar_artists(artist_id: str):
    """
    获取与指定艺人相似的艺人
    args:
        artist_id: 艺人 ID (网易云)
    """
    logger.info(f"Calling cloud_music_get_similar_artists: artist={artist_id}")
    result = get_similar_artists(artist_id)
    if result["success"]:
        return result["artists"]
    else:
        return f"获取失败: {result.get('error')}"


if __name__ == "__main__":
    mcp.run()
