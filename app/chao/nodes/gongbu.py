from app.chao.state import ChaoState

def gongbu_execute(state: ChaoState) -> ChaoState:
    return {
        **state,
        "status": "IMPLEMENTING",
        "implementation_result": {
            "summary": "MVP 阶段暂不自动改代码，只生成执行计划。",
            "changed_files": [],
            "risk": "未实际修改代码。",
        },
    }
