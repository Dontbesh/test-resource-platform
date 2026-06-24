# 三期 LLM 必须支持 tool calling

实际计划使用的 OpenAI-compatible 模型均支持 tool/function calling，因此三期直接采用原生工具调用。平台只暴露带 JSON Schema 参数的白名单工具：查询类工具可在当前用户权限内执行，占用、释放和延期等写工具只生成操作草案，用户确认后仍通过业务 API 完成权限、幂等和审计校验。
