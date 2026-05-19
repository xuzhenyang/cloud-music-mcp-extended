# cloud-music-mcp 扩展开发任务

## 目标

在 [xuzhenyang/cloud-music-mcp](https://github.com/xuzhenyang/cloud-music-mcp) 基础上，新增 3 个 MCP 工具，支持歌单创建、批量收藏歌曲、获取相似歌曲推荐。

---

## 改动范围

只修改 2 个源码文件 + 1 个文档文件：

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/cloud_music_mcp/api.py` | 追加 | 新增 4 个 API 函数 |
| `src/cloud_music_mcp/main.py` | 追加 + 修改 import | 新增 3 个 MCP 工具注册 |
| `README.md` | 更新 | 文档同步 |

---

## 一、api.py 新增内容

在文件末尾（`search_song` 函数之后）追加以下函数：

### 1. create_playlist

```python
def create_playlist(name: str, privacy: bool = False):
    """创建歌单"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    
    try:
        result = apis.playlist.SetCreatePlaylist(name, privacy)
        if result['code'] == 200:
            return {
                "success": True,
                "playlist_id": result.get('id'),
                "name": result.get('name'),
                "message": f"歌单 '{name}' 创建成功"
            }
        else:
            return {"success": False, "error": f"API 错误: {result.get('message', '未知错误')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- 调用 pyncm: `apis.playlist.SetCreatePlaylist(name, privacy)`
- 返回: 包含 `playlist_id` 的成功响应

### 2. add_tracks_to_playlist

```python
def add_tracks_to_playlist(playlist_id, track_ids):
    """批量添加歌曲到歌单"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    
    try:
        # 确保是列表
        ids = track_ids if isinstance(track_ids, list) else [track_ids]
        result = apis.playlist.SetManipulatePlaylistTracks(ids, playlist_id, op="add")
        if result['code'] == 200:
            return {
                "success": True,
                "message": f"成功添加 {len(ids)} 首歌曲到歌单",
                "playlist_id": playlist_id
            }
        else:
            return {"success": False, "error": f"API 错误: {result.get('message', '未知错误')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- 调用 pyncm: `apis.playlist.SetManipulatePlaylistTracks(ids, playlist_id, op="add")`
- `track_ids` 可以传单个 ID 或列表，函数内部统一转成列表

### 3. _GetSimilarSongsInternal (Weapi 装饰器内部函数)

```python
@apis.WeapiCryptoRequest
def _GetSimilarSongsInternal(song_id, limit=30):
    """内部函数：获取相似歌曲（Weapi）"""
    return "/weapi/v1/discovery/simiSong", {
        "songid": str(song_id),
        "limit": str(limit)
    }
```

- 使用 `apis.WeapiCryptoRequest` 装饰器
- API 路径: `/weapi/v1/discovery/simiSong`
- 参数: `songid` (str), `limit` (str)

### 4. get_similar_songs (包装函数)

```python
def get_similar_songs(song_id, limit=20):
    """获取与指定歌曲相似的歌"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    
    try:
        result = _GetSimilarSongsInternal(song_id, limit)
        if result['code'] == 200 and 'songs' in result:
            songs = []
            for song in result['songs']:
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['artists'][0]['name'] if song.get('artists') else "未知",
                    "album": song['album']['name'] if song.get('album') else ""
                })
            return {"success": True, "songs": songs}
        else:
            return {"success": False, "error": f"API 错误: {result.get('message', '未知错误')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
```

- 检查登录态
- 调用内部 `_GetSimilarSongsInternal`
- 提取 `result['songs']`，格式化返回

---

## 二、main.py 改动

### 1. 修改 import

将现有的 API import：

```python
from cloud_music_mcp.api import (
    get_daily_recommendations,
    get_user_playlists,
    search_song,
)
```

改为：

```python
from cloud_music_mcp.api import (
    get_daily_recommendations,
    get_user_playlists,
    search_song,
    create_playlist,
    add_tracks_to_playlist,
    get_similar_songs,
)
```

### 2. 在文件末尾（`cloud_music_play` 之后、`if __name__` 之前）追加 3 个工具：

```python
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
```

---

## 三、README.md 更新点

1. **功能特性列表**：新增一条 "📁 歌单管理：支持创建歌单、批量收藏歌曲，以及获取相似歌曲推荐"

2. **工具列表表格**：追加 3 行：

| 工具名称 | 参数 | 功能描述 |
|---------|------|---------|
| `cloud_music_create_playlist` | `name`: 歌单名称, `privacy`: 是否隐私歌单 | 创建新的网易云歌单 |
| `cloud_music_add_tracks` | `playlist_id`: 歌单ID, `track_ids`: 歌曲ID列表 | 批量添加歌曲到指定歌单 |
| `cloud_music_get_similar_songs` | `song_id`: 歌曲ID, `limit`: 返回数量(默认20) | 获取与指定歌曲相似的推荐歌曲 |

3. **使用示例**：新增歌单管理和相似推荐的示例代码块

4. **仓库地址**：将 `Code-MonkeyZhang` 改为 `xuzhenyang`

---

## 验证方法

改完后本地测试：

```bash
cd cloud-music-mcp
uv pip install -e .

# 先测试登录
cloud-music-mcp
# 然后调用 cloud_music_login，扫码

# 测试创建歌单
# 调用 cloud_music_create_playlist 参数: {"name": "测试歌单"}

# 测试添加歌曲
# 先搜索一首歌获取 ID，然后调用 cloud_music_add_tracks
# 参数: {"playlist_id": "刚才的歌单ID", "track_ids": ["歌曲ID"]}

# 测试相似推荐
# 调用 cloud_music_get_similar_songs 参数: {"song_id": "29732235"}
```

---

## 参考源码（pyncm 底层 API）

- `apis.playlist.SetCreatePlaylist(name, privacy)` — 创建歌单
- `apis.playlist.SetManipulatePlaylistTracks(trackIds, playlistId, op="add")` — 添加歌曲
- `apis.WeapiCryptoRequest` 装饰器 — 用于自定义 API 请求
- 相似歌曲 API 路径: `/weapi/v1/discovery/simiSong`，参数 `songid` + `limit`
