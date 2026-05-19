import pyncm
from pyncm import apis

# 尝试相对导入，fallback到绝对导入（兼容直接运行和作为包导入）
try:
    from .auth import load_session
except ImportError:
    from auth import load_session

def get_daily_recommendations():
    """获取每日推荐歌曲"""
    # 确保已登录
    if not load_session()[0]:
        return {"success": False, "error": "未登录，请先调用 login 工具"}
    
    try:
        # 定义内部函数并使用 WeapiCryptoRequest 装饰
        @apis.WeapiCryptoRequest
        def GetDailyRecommendInternal():
            return "/weapi/v1/discovery/recommend/songs", {"limit": 30, "offset": 0, "total": True}
        
        # 调用内部函数 (session 会被自动注入)
        result = GetDailyRecommendInternal()
        
        if result['code'] == 200:
            songs = []
            for song in result['recommend']:
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['artists'][0]['name'] if song['artists'] else "未知",
                    "album": song['album']['name'] if song['album'] else ""
                })
            return {"success": True, "songs": songs}
        else:
            return {"success": False, "error": f"API 错误: {result.get('message', '未知错误')}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_user_playlists():
    """获取用户的歌单"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    
    try:
        # 获取当前用户 ID
        user_info = apis.login.GetCurrentLoginStatus()
        uid = user_info['profile']['userId']
        
        result = apis.user.GetUserPlaylists(uid)
        if result['code'] == 200:
            playlists = []
            for pl in result['playlist']:
                playlists.append({
                    "id": pl['id'],
                    "name": pl['name'],
                    "count": pl['trackCount'],
                    "creator": pl['creator']['nickname'],
                    "is_mine": pl['creator']['userId'] == uid
                })
            return {"success": True, "playlists": playlists}
        else:
            return {"success": False, "error": "API 请求失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def search_song(keyword, limit=5):
    """搜索歌曲"""
    # 搜索不需要登录，但登录后结果更准
    load_session() 
    try:
        result = apis.cloudsearch.GetSearchResult(keyword, stype=1, limit=limit)
        if result['code'] == 200 and 'result' in result and 'songs' in result['result']:
            songs = []
            for song in result['result']['songs']:
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['ar'][0]['name'] if song['ar'] else "未知"
                })
            return {"success": True, "songs": songs}
        return {"success": False, "error": "未找到结果"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


def add_tracks_to_playlist(playlist_id, track_ids):
    """批量添加歌曲到歌单
    
    注意：网易云 API SetManipulatePlaylistTracks 的 add 操作会把歌曲列表
    逆序添加到歌单中（后传入的排在前面）。因此我们在调用 API 前先将
    track_ids 反转，以保证歌单中的最终顺序与传入顺序一致。
    """
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    
    try:
        # 确保是列表
        ids = track_ids if isinstance(track_ids, list) else [track_ids]
        # 反转顺序：API 内部会再次反转，最终保持原始顺序
        ids_reversed = list(reversed(ids))
        result = apis.playlist.SetManipulatePlaylistTracks(ids_reversed, playlist_id, op="add")
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


@apis.WeapiCryptoRequest
def _GetSimilarSongsInternal(song_id, limit=30):
    """内部函数：获取相似歌曲（Weapi）"""
    return "/weapi/v1/discovery/simiSong", {
        "songid": str(song_id),
        "limit": str(limit)
    }


@apis.WeapiCryptoRequest
def _GetSimilarArtistsInternal(artist_id):
    """内部函数：获取相似艺人（Weapi）"""
    return "/weapi/discovery/simiArtist", {
        "artistid": str(artist_id),
    }


def get_audio_url(song_id):
    """获取歌曲音频下载链接"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录，请先调用 cloud_music_login 工具", "error_code": "NOT_LOGGED_IN"}
    try:
        result = apis.track.GetTrackAudio([str(song_id)])
        if result['code'] == 200 and 'data' in result and result['data']:
            data = result['data'][0]
            if data.get('url'):
                return {
                    "success": True,
                    "id": str(data['id']),
                    "url": data['url'],
                    "br": data.get('br'),
                    "type": data.get('type'),
                    "duration": data.get('time'),  # ms
                }
            # 区分：API正常返回但音频为空（VIP/版权限制）
            return {"success": False, "error": "该歌曲暂无音频资源（可能为 VIP 独占或版权限制）", "error_code": "NO_AUDIO_RESOURCE"}
        # API 本身报错（code != 200）
        return {"success": False, "error": f"API 返回错误: {result.get('message', '未知错误')}", "error_code": "API_ERROR", "api_code": result.get('code')}
    except Exception as e:
        return {"success": False, "error": str(e), "error_code": "EXCEPTION"}


def get_artist_tracks(artist_id, limit=30):
    """获取艺术家的热门歌曲"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = apis.artist.GetArtistTracks(artist_id, limit=limit, offset=0)
        if result['code'] == 200 and 'songs' in result:
            songs = []
            for song in result['songs']:
                # GetArtistTracks 返回的字段名是 artists / album
                artists = song.get('artists', song.get('ar', []))
                album_info = song.get('album', song.get('al', {}))
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": artists[0]['name'] if artists else "未知",
                    "album": album_info.get('name', '') if album_info else ""
                })
            return {"success": True, "songs": songs}
        return {"success": False, "error": "获取艺术家歌曲失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_album_songs(album_id):
    """获取专辑的歌曲列表"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = apis.album.GetAlbumInfo(album_id)
        if result['code'] == 200 and 'songs' in result:
            songs = []
            for song in result['songs']:
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['ar'][0]['name'] if song.get('ar') else "未知",
                    "album": result.get('album', {}).get('name', '')
                })
            return {"success": True, "songs": songs}
        return {"success": False, "error": "获取专辑歌曲失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_song_detail(song_id):
    """获取歌曲详情"""
    load_session()
    try:
        result = apis.track.GetTrackDetail([str(song_id)])
        if result['code'] == 200 and 'songs' in result and result['songs']:
            song = result['songs'][0]
            # pyncm GetTrackDetail 返回的字段名: ar=artists, al=album
            ar = song.get('ar', [])
            al = song.get('al', {})
            return {
                "success": True,
                "id": str(song['id']),
                "name": song['name'],
                "artist": ar[0]['name'] if ar else "未知",
                "artist_id": ar[0]['id'] if ar else None,
                "album": al.get('name', '') if al else "",
                "album_id": al.get('id') if al else None,
            }
        return {"success": False, "error": "未找到歌曲"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_similar_artists(artist_id):
    """获取与指定艺人相似的艺人"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = _GetSimilarArtistsInternal(artist_id)
        if result['code'] == 200 and 'artists' in result:
            artists = []
            for artist in result['artists']:
                artists.append({
                    "id": artist['id'],
                    "name": artist['name'],
                })
            return {"success": True, "artists": artists}
        return {"success": False, "error": "获取相似艺人失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _safe_get_title(resource: dict) -> str:
    """安全地从 resource 中提取 title"""
    ui = resource.get('uiElement') or {}
    main = ui.get('mainTitle') or {}
    return main.get('title', '')


def get_song_wiki(song_id):
    """获取歌曲音乐百科信息（曲风、标签等）"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = _GetSongWikiInternal(song_id)
        if result.get('code') == 200:
            data = result.get('data', {})
            blocks = data.get('blocks', [])
            genres = []
            tags = []
            for block in blocks:
                for creative in block.get('creatives') or []:
                    if not creative:
                        continue
                    ctype = creative.get('creativeType', '')
                    for r in creative.get('resources') or []:
                        if not r:
                            continue
                        title = _safe_get_title(r)
                        if title:
                            if ctype == 'songTag':
                                genres.append(title)
                            elif ctype == 'songBizTag':
                                tags.append(title)
            return {
                "success": True,
                "song_id": str(song_id),
                "genres": genres,
                "tags": tags,
            }
        return {"success": False, "error": "获取音乐百科失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@apis.WeapiCryptoRequest
def _GetSongWikiInternal(song_id):
    """内部函数：获取歌曲音乐百科（Weapi）"""
    return "/weapi/song/play/about/block/page", {
        "songId": str(song_id),
    }


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


def get_style_list():
    """获取网易云曲风标签完整层级树"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = _GetStyleListInternal()
        if result.get('code') == 200:
            return {
                "success": True,
                "tags": result.get('data', []),
            }
        return {"success": False, "error": "获取曲风列表失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@apis.WeapiCryptoRequest
def _GetStyleListInternal():
    """内部函数：获取曲风标签列表（Weapi）"""
    return "/api/tag/list/get", {}


def get_style_songs(tag_id, size=20, sort=0):
    """获取指定曲风标签下的歌曲"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = _GetStyleSongsInternal(tag_id, size, sort)
        if result.get('code') == 200:
            data = result.get('data', {})
            songs = []
            for song in data.get('songs', []):
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['artists'][0]['name'] if song.get('artists') else "未知",
                })
            return {
                "success": True,
                "tag_id": str(tag_id),
                "songs": songs,
                "has_more": data.get('hasMore', False),
            }
        return {"success": False, "error": "获取曲风歌曲失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@apis.WeapiCryptoRequest
def _GetStyleSongsInternal(tag_id, size=20, sort=0):
    """内部函数：获取曲风标签下的歌曲（Weapi）"""
    return "/api/style-tag/home/song", {
        "tagId": str(tag_id),
        "size": size,
        "sort": sort,
        "cursor": 0,
    }


def search_playlist(keyword, limit=10):
    """搜索歌单"""
    load_session()
    try:
        result = apis.cloudsearch.GetSearchResult(keyword, stype=1000, limit=limit)
        if result['code'] == 200 and 'result' in result:
            playlists = result['result'].get('playlists', [])
            return {
                "success": True,
                "playlists": [
                    {
                        "id": pl['id'],
                        "name": pl['name'],
                        "track_count": pl.get('trackCount', 0),
                        "creator": pl.get('creator', {}).get('nickname', '未知'),
                    }
                    for pl in playlists
                ],
            }
        return {"success": False, "error": "未找到歌单"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_playlist_songs(playlist_id, limit=50):
    """获取歌单中的所有歌曲"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
    try:
        result = apis.playlist.GetPlaylistAllTracks(playlist_id)
        if result['code'] == 200 and 'songs' in result:
            songs = []
            for song in result['songs'][:limit]:
                songs.append({
                    "id": song['id'],
                    "name": song['name'],
                    "artist": song['ar'][0]['name'] if song.get('ar') else "未知",
                })
            return {"success": True, "songs": songs}
        return {"success": False, "error": "获取歌单歌曲失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}
