"""
ArchAutoMap QGIS 플러그인 강제 리로드 스크립트
QGIS Python Console에서 실행:
    exec(open(r"C:\Users\nuri9\Documents\archautomap\dev_reload.py").read())
"""
import sys
import importlib

PLUGIN_NAME = "ArchAutoMap"


def reload_archautomap():
    from qgis.utils import plugins, unloadPlugin, loadPlugin, startPlugin

    print(f"\n{'='*50}")
    print(f"[{PLUGIN_NAME}] 리로드 시작...")

    # 1. 현재 로드돼 있으면 언로드
    if PLUGIN_NAME in plugins:
        try:
            unloadPlugin(PLUGIN_NAME)
            print(f"  ✓ 언로드 완료")
        except Exception as e:
            print(f"  ⚠ 언로드 중 오류 (무시): {e}")
    else:
        print(f"  - 이미 언로드된 상태")

    # 2. sys.modules 에서 ArchAutoMap 관련 모든 모듈 제거
    keys_to_remove = [
        k for k in sys.modules
        if k == PLUGIN_NAME
        or k.startswith(PLUGIN_NAME + ".")
        or k == PLUGIN_NAME.lower()
        or k.startswith(PLUGIN_NAME.lower() + ".")
    ]
    for k in keys_to_remove:
        del sys.modules[k]
    print(f"  ✓ {len(keys_to_remove)}개 모듈 캐시 제거: {keys_to_remove[:5]}{'...' if len(keys_to_remove) > 5 else ''}")

    # 3. __pycache__ 의 .pyc 파일은 Python이 소스 수정 시간을 확인하므로
    #    별도 삭제 없이도 sys.modules 정리만으로 최신 코드가 로드됩니다.

    # 4. 다시 로드 & 시작
    try:
        loadPlugin(PLUGIN_NAME)
        print(f"  ✓ loadPlugin 완료")
    except Exception as e:
        print(f"  ✗ loadPlugin 실패: {e}")
        return

    try:
        startPlugin(PLUGIN_NAME)
        print(f"  ✓ startPlugin 완료")
    except Exception as e:
        print(f"  ✗ startPlugin 실패: {e}")
        return

    print(f"[{PLUGIN_NAME}] 리로드 완료 ✅")
    print(f"{'='*50}\n")

    # 5. 도구모음 버튼 클릭해 창 열기
    if PLUGIN_NAME in plugins:
        plugin_instance = plugins[PLUGIN_NAME]
        if hasattr(plugin_instance, "show_dock"):
            plugin_instance.show_dock()


reload_archautomap()
