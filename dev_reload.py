"""
ArchAutoMap 개발용 QGIS 플러그인 즉시 리로드 스크립트
=======================================================

QGIS Python 콘솔에서 이 파일의 내용을 붙여넣거나 exec(open(...).read())로 실행하세요.

사용법 (QGIS Python Console):
    exec(open(r"C:\Users\nuri9\Documents\archautomap\dev_reload.py").read())
"""

import importlib
import sys

PLUGIN_PACKAGE = "ArchAutoMap"


def reload_archautomap():
    """ArchAutoMap 플러그인을 QGIS를 재시작하지 않고 즉시 리로드합니다."""
    from qgis.utils import plugins, reloadPlugin, loadPlugin, startPlugin

    # 기존 플러그인 언로드
    if PLUGIN_PACKAGE in plugins:
        print(f"[ArchAutoMap] 기존 플러그인 언로드 중...")
        plugins[PLUGIN_PACKAGE].unload()

    # sys.modules에서 관련 모듈 전부 제거 (캐시 무효화)
    mods_to_remove = [
        key for key in sys.modules
        if key == PLUGIN_PACKAGE or key.startswith(PLUGIN_PACKAGE + ".")
    ]
    for mod in mods_to_remove:
        del sys.modules[mod]
    print(f"[ArchAutoMap] {len(mods_to_remove)}개 모듈 캐시 제거 완료")

    # 플러그인 다시 로드
    reloadPlugin(PLUGIN_PACKAGE)
    print(f"[ArchAutoMap] 플러그인 리로드 완료 ✅")
    print(f"[ArchAutoMap] QGIS 메뉴 또는 툴바에서 ArchAutoMap을 다시 실행하세요.")


reload_archautomap()
