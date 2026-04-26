import pyncm
from pyncm import apis
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


@apis.WeapiCryptoRequest
def _GetSimilarSongsInternal(song_id, limit=30):
    """内部函数：获取相似歌曲（Weapi）"""
    return "/weapi/v1/discovery/simiSong", {
        "songid": str(song_id),
        "limit": str(limit)
    }


def get_audio_url(song_id):
    """获取歌曲音频下载链接"""
    if not load_session()[0]:
        return {"success": False, "error": "未登录"}
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
            return {"success": False, "error": "该歌曲暂无音频资源（可能为 VIP 独占或版权限制）"}
        return {"success": False, "error": "获取音频链接失败"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            return {
                "success": True,
                "id": str(song['id']),
                "name": song['name'],
                "artist": song['ar'][0]['name'] if song.get('ar') else "未知",
                "artist_id": song['ar'][0]['id'] if song.get('ar') else None,
                "album": song['album']['name'] if song.get('album') else "",
                "album_id": song['album']['id'] if song.get('album') else None,
            }
        return {"success": False, "error": "未找到歌曲"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
