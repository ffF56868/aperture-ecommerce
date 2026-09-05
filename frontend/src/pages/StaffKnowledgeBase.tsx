import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Database,
  FileText,
  Globe2,
  Link2,
  Loader2,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
  Upload,
  XCircle,
} from "lucide-react";
import { Navigate } from "react-router-dom";
import { afterSalesApi } from "@/api/afterSales";
import { getErrorMessage } from "@/api/client";
import { productsApi } from "@/api/products";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Container } from "@/components/ui/Container";
import { Spinner } from "@/components/ui/Skeleton";
import { useAuth } from "@/hooks/useAuth";
import type { StaffKnowledgeDocument, StaffKnowledgeSearchResponse } from "@/types";

type SourceMode = "TEXT" | "FILE" | "WEBPAGE";
type ScopeMode = "GLOBAL" | "CATEGORY" | "PRODUCT";

const STATUS_LABEL: Record<string, string> = {
  READY: "已就绪",
  PENDING: "待索引",
  PROCESSING: "索引中",
  FAILED: "索引失败",
};

const STATUS_VARIANT: Record<string, "success" | "accent" | "coral" | "danger"> = {
  READY: "success",
  PENDING: "accent",
  PROCESSING: "coral",
  FAILED: "danger",
};

function statusIcon(status: string) {
  if (status === "READY") return <CheckCircle2 className="h-3.5 w-3.5" />;
  if (status === "FAILED") return <XCircle className="h-3.5 w-3.5" />;
  return <Loader2 className="h-3.5 w-3.5" />;
}

function scopeLabel(document: StaffKnowledgeDocument) {
  if (document.product) return `商品：${document.product.name}`;
  if (document.product_category) return `分类：${document.product_category.name}`;
  return "全局规则";
}

function sourceLabel(document: StaffKnowledgeDocument) {
  if (document.source_type === "FILE") return document.file_name || "上传文件";
  if (document.source_type === "WEBPAGE") return document.source_url || "网页来源";
  return "直接文本";
}

export function StaffKnowledgeBase() {
  const { isAuthenticated, user } = useAuth();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [searchDraft, setSearchDraft] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [sourceMode, setSourceMode] = useState<SourceMode>("TEXT");
  const [scopeMode, setScopeMode] = useState<ScopeMode>("GLOBAL");
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("售后规则");
  const [sourceLabelValue, setSourceLabelValue] = useState("");
  const [content, setContent] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [productId, setProductId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState("");
  const [editingDocument, setEditingDocument] = useState<StaffKnowledgeDocument | null>(null);
  const [retrievalQuestion, setRetrievalQuestion] = useState("");
  const [retrievalScope, setRetrievalScope] = useState<ScopeMode>("GLOBAL");
  const [retrievalProductId, setRetrievalProductId] = useState("");
  const [retrievalCategoryId, setRetrievalCategoryId] = useState("");
  const [retrievalResult, setRetrievalResult] = useState<StaffKnowledgeSearchResponse | null>(null);

  const documentsQuery = useQuery({
    queryKey: ["staff-knowledge-documents", search],
    queryFn: () => afterSalesApi.listStaffKnowledgeDocuments(search ? { search } : {}),
    enabled: isAuthenticated && Boolean(user?.is_staff),
    refetchInterval: (query) => (query.state.data?.summary.processing ? 4000 : false),
  });
  const categoriesQuery = useQuery({
    queryKey: ["knowledge-product-categories"],
    queryFn: productsApi.listCategories,
    enabled: isAuthenticated && Boolean(user?.is_staff),
  });
  const productsQuery = useQuery({
    queryKey: ["knowledge-products"],
    queryFn: () => productsApi.listProducts({ page: 1 }),
    enabled: isAuthenticated && Boolean(user?.is_staff) && (scopeMode === "PRODUCT" || retrievalScope === "PRODUCT"),
  });

  const createMutation = useMutation({
    mutationFn: afterSalesApi.createStaffKnowledgeDocument,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["staff-knowledge-documents"] });
      setShowForm(false);
      setTitle("");
      setSourceLabelValue("");
      setContent("");
      setSourceUrl("");
      setProductId("");
      setCategoryId("");
      setFile(null);
      setFormError("");
      setEditingDocument(null);
    },
  });
  const updateMutation = useMutation({
    mutationFn: ({ documentId, payload }: { documentId: string; payload: FormData | Record<string, unknown> }) =>
      afterSalesApi.updateStaffKnowledgeDocument(documentId, payload),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["staff-knowledge-documents"] }),
  });
  const reindexMutation = useMutation({
    mutationFn: afterSalesApi.reindexStaffKnowledgeDocument,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["staff-knowledge-documents"] }),
  });
  const deleteMutation = useMutation({
    mutationFn: afterSalesApi.deleteStaffKnowledgeDocument,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["staff-knowledge-documents"] }),
  });
  const retrievalMutation = useMutation({
    mutationFn: afterSalesApi.searchStaffKnowledge,
    onSuccess: (result) => setRetrievalResult(result),
  });

  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_staff) return <Navigate to="/" replace />;

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSearch(searchDraft.trim());
  };

  const submitRetrievalTest = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = retrievalQuestion.trim();
    if (question.length < 2 || retrievalMutation.isPending) return;
    retrievalMutation.mutate({
      question,
      limit: 5,
      product_id: retrievalScope === "PRODUCT" && retrievalProductId ? Number(retrievalProductId) : null,
      category_id: retrievalScope === "CATEGORY" && retrievalCategoryId ? Number(retrievalCategoryId) : null,
    });
  };

  const submitCreate = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError("");
    if (!title.trim()) {
      setFormError("请填写文档标题。");
      return;
    }
    const hasNewSource =
      (sourceMode === "TEXT" && content.trim().length >= 2) ||
      (sourceMode === "FILE" && Boolean(file)) ||
      (sourceMode === "WEBPAGE" && Boolean(sourceUrl.trim()));
    if (!editingDocument && sourceMode === "TEXT" && content.trim().length < 2) {
      setFormError("文本内容至少需要 2 个字符。");
      return;
    }
    if (!editingDocument && sourceMode === "FILE" && !file) {
      setFormError("请选择一个 .txt、.md、.docx 或 .pdf 文件。");
      return;
    }
    if (!editingDocument && sourceMode === "WEBPAGE" && !sourceUrl.trim()) {
      setFormError("请填写网页 URL。");
      return;
    }
    if (editingDocument && !hasNewSource && sourceMode !== editingDocument.source_type) {
      setFormError("切换知识来源时，请同时提供新的文本、文件或网页地址。");
      return;
    }
    if (editingDocument) {
      const scopePayload = {
        product_id: scopeMode === "PRODUCT" && productId ? Number(productId) : null,
        product_category_id: scopeMode === "CATEGORY" && categoryId ? Number(categoryId) : null,
      };
      if (!hasNewSource) {
        updateMutation.mutate({
          documentId: editingDocument.id,
          payload: {
            title: title.trim(),
            category: category.trim() || "售后规则",
            source_label: sourceLabelValue.trim(),
            ...scopePayload,
          },
        });
        return;
      }
      const payload = new FormData();
      payload.append("title", title.trim());
      payload.append("category", category.trim() || "售后规则");
      payload.append("source_label", sourceLabelValue.trim());
      payload.append("product_id", scopePayload.product_id?.toString() ?? "");
      payload.append("product_category_id", scopePayload.product_category_id?.toString() ?? "");
      if (sourceMode === "TEXT" && content.trim()) payload.append("content", content);
      if (sourceMode === "WEBPAGE" && sourceUrl.trim()) payload.append("source_url", sourceUrl.trim());
      if (sourceMode === "FILE" && file) payload.append("file", file);
      updateMutation.mutate({ documentId: editingDocument.id, payload });
      return;
    }
    const formData = new FormData();
    formData.append("title", title.trim());
    formData.append("category", category.trim() || "售后规则");
    if (sourceLabelValue.trim()) formData.append("source_label", sourceLabelValue.trim());
    if (sourceMode === "TEXT") formData.append("content", content);
    if (sourceMode === "WEBPAGE") formData.append("source_url", sourceUrl.trim());
    if (sourceMode === "FILE" && file) formData.append("file", file);
    if (scopeMode === "PRODUCT" && productId) formData.append("product_id", productId);
    if (scopeMode === "CATEGORY" && categoryId) formData.append("product_category_id", categoryId);
    createMutation.mutate(formData);
  };

  const openCreateForm = () => {
    setEditingDocument(null);
    setSourceMode("TEXT");
    setScopeMode("GLOBAL");
    setTitle("");
    setCategory("售后规则");
    setSourceLabelValue("");
    setContent("");
    setSourceUrl("");
    setProductId("");
    setCategoryId("");
    setFile(null);
    setFormError("");
    setShowForm(true);
  };

  const openEditForm = (document: StaffKnowledgeDocument) => {
    setEditingDocument(document);
    setSourceMode(document.source_type);
    setScopeMode(document.product ? "PRODUCT" : document.product_category ? "CATEGORY" : "GLOBAL");
    setTitle(document.title);
    setCategory(document.category);
    setSourceLabelValue(document.source_label);
    setContent("");
    setSourceUrl(document.source_url);
    setProductId(document.product?.id ?? "");
    setCategoryId(document.product_category?.id ?? "");
    setFile(null);
    setFormError("");
    setShowForm(true);
  };

  const data = documentsQuery.data;
  return (
    <Container className="py-6 sm:py-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-accent/15 text-accent"><Database className="h-5 w-5" /></div>
          <div><h1 className="font-display text-2xl font-semibold text-ink">RAG 知识库</h1><p className="text-sm text-ink-muted">仅管理员可见 · 文档解析、Milvus 向量化与售后规则范围管理</p></div>
        </div>
        <Button onClick={showForm ? () => setShowForm(false) : openCreateForm}><Plus className="h-4 w-4" />{showForm ? "收起编辑" : "上传知识"}</Button>
      </div>

      {data && (
        <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[["全部文档", data.summary.total], ["已就绪", data.summary.ready], ["待处理", data.summary.pending], ["索引中", data.summary.processing], ["失败", data.summary.failed]].map(([label, value]) => (
            <Card key={label as string}><CardContent className="p-4"><p className="text-xs text-ink-muted">{label}</p><p className="mt-2 font-display text-2xl font-semibold text-ink">{value}</p></CardContent></Card>
          ))}
        </div>
      )}

      {showForm && (
        <Card className="mb-5">
          <CardContent className="p-5">
            <div className="mb-4 flex items-center gap-2"><Upload className="h-4 w-4 text-accent" /><h2 className="text-base font-semibold text-ink">{editingDocument ? "编辑知识文档" : "新增知识文档"}</h2></div>
            <form onSubmit={submitCreate} className="grid gap-4 lg:grid-cols-2">
              <div className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="text-sm text-ink-muted">文档标题<input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} placeholder="例如：夏季短袖退换货规则" className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent" /></label>
                  <label className="text-sm text-ink-muted">知识分类<input value={category} onChange={(event) => setCategory(event.target.value)} maxLength={64} className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent" /></label>
                </div>
                <label className="text-sm text-ink-muted">引用名称<span className="ml-1 text-xs text-ink-faint">可选，默认使用标题</span><input value={sourceLabelValue} onChange={(event) => setSourceLabelValue(event.target.value)} maxLength={160} placeholder="用户回答中显示的来源名称" className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent" /></label>
                <div><p className="text-sm text-ink-muted">知识来源</p><div className="mt-2 flex flex-wrap gap-2"><Button type="button" size="sm" variant={sourceMode === "TEXT" ? "secondary" : "outline"} onClick={() => setSourceMode("TEXT")}><FileText className="h-4 w-4" />直接文本</Button><Button type="button" size="sm" variant={sourceMode === "FILE" ? "secondary" : "outline"} onClick={() => setSourceMode("FILE")}><Upload className="h-4 w-4" />文件</Button><Button type="button" size="sm" variant={sourceMode === "WEBPAGE" ? "secondary" : "outline"} onClick={() => setSourceMode("WEBPAGE")}><Globe2 className="h-4 w-4" />网页</Button></div></div>
                {sourceMode === "TEXT" && <label className="block text-sm text-ink-muted">知识内容<textarea value={content} onChange={(event) => setContent(event.target.value)} rows={9} placeholder="输入经过审核的售后规则、尺码、洗护或服务说明" className="mt-2 w-full resize-y rounded-md border border-border-strong bg-bg px-3 py-2 leading-6 text-ink outline-none focus:border-accent" /></label>}
                {sourceMode === "FILE" && <label className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-strong bg-bg px-4 text-center text-sm text-ink-muted hover:border-accent"><Upload className="h-5 w-5 text-accent" /><span>{file ? file.name : "选择 .txt、.md、.docx 或 .pdf"}</span><input type="file" accept=".txt,.md,.docx,.pdf,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(event) => setFile(event.target.files?.[0] ?? null)} className="sr-only" /></label>}
                {sourceMode === "WEBPAGE" && <label className="text-sm text-ink-muted">网页 URL<input type="url" value={sourceUrl} onChange={(event) => setSourceUrl(event.target.value)} placeholder="https://example.com/after-sales-policy" className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent" /></label>}
              </div>
              <div className="space-y-4">
                <div><p className="text-sm text-ink-muted">适用范围</p><div className="mt-2 flex flex-wrap gap-2"><Button type="button" size="sm" variant={scopeMode === "GLOBAL" ? "secondary" : "outline"} onClick={() => setScopeMode("GLOBAL")}>全局规则</Button><Button type="button" size="sm" variant={scopeMode === "CATEGORY" ? "secondary" : "outline"} onClick={() => setScopeMode("CATEGORY")}>指定分类</Button><Button type="button" size="sm" variant={scopeMode === "PRODUCT" ? "secondary" : "outline"} onClick={() => setScopeMode("PRODUCT")}>指定商品</Button></div></div>
                {scopeMode === "CATEGORY" && <label className="text-sm text-ink-muted">商品分类<select value={categoryId} onChange={(event) => setCategoryId(event.target.value)} className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent"><option value="">请选择分类</option>{(categoriesQuery.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
                {scopeMode === "PRODUCT" && <label className="text-sm text-ink-muted">商品<select value={productId} onChange={(event) => setProductId(event.target.value)} className="mt-2 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-ink outline-none focus:border-accent"><option value="">请选择商品</option>{(productsQuery.data?.results ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
                <div className="border-l-2 border-accent bg-accent/5 px-3 py-3 text-sm leading-6 text-ink-muted">文档会先保存到 PostgreSQL，再由 Celery 异步解析切片并写入 Milvus。只有“已就绪”且开启检索的文档会被 Agent 使用。编辑时不提供新来源则只更新文档资料。</div>
                {formError && <p className="text-sm text-danger">{formError}</p>}
                {createMutation.isError && <p className="text-sm text-danger">上传失败：{getErrorMessage(createMutation.error)}</p>}
                {updateMutation.isError && <p className="text-sm text-danger">保存失败：{getErrorMessage(updateMutation.error)}</p>}
                <div className="flex justify-end gap-2"><Button type="button" variant="ghost" onClick={() => setShowForm(false)}>取消</Button><Button type="submit" isLoading={createMutation.isPending || updateMutation.isPending}><Upload className="h-4 w-4" />{editingDocument ? "保存修改" : "提交并建立索引"}</Button></div>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      <Card className="mb-5">
        <CardContent className="p-5">
          <div className="mb-4 flex items-center gap-2">
            <Search className="h-4 w-4 text-accent" />
            <div><h2 className="text-base font-semibold text-ink">检索测试</h2><p className="text-xs text-ink-muted">先确认切片、相似度和引用来源，再去售后助手中验证回答。</p></div>
          </div>
          <form onSubmit={submitRetrievalTest} className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_170px_auto]">
            <input value={retrievalQuestion} onChange={(event) => setRetrievalQuestion(event.target.value)} maxLength={500} placeholder="例如：退货退款需要满足什么条件？" className="h-10 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent" />
            <select value={retrievalScope} onChange={(event) => setRetrievalScope(event.target.value as ScopeMode)} className="h-10 rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent" aria-label="检索范围">
              <option value="GLOBAL">全局规则</option><option value="CATEGORY">指定分类</option><option value="PRODUCT">指定商品</option>
            </select>
            <Button type="submit" isLoading={retrievalMutation.isPending}><Search className="h-4 w-4" />测试检索</Button>
          </form>
          {retrievalScope === "CATEGORY" && <select value={retrievalCategoryId} onChange={(event) => setRetrievalCategoryId(event.target.value)} className="mt-3 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent" aria-label="检索商品分类"><option value="">请选择商品分类</option>{(categoriesQuery.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}
          {retrievalScope === "PRODUCT" && <select value={retrievalProductId} onChange={(event) => setRetrievalProductId(event.target.value)} className="mt-3 h-10 w-full rounded-md border border-border-strong bg-bg px-3 text-sm text-ink outline-none focus:border-accent" aria-label="检索商品"><option value="">请选择商品</option>{(productsQuery.data?.results ?? []).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}
          {retrievalMutation.isError && <p className="mt-3 text-sm text-danger">检索失败：{getErrorMessage(retrievalMutation.error)}</p>}
          {retrievalResult && <div className="mt-4 border-t border-border pt-4"><div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className={retrievalResult.requires_human_escalation ? "text-danger" : "text-success"}>{retrievalResult.message}</span><span className="text-xs text-ink-faint">命中 {retrievalResult.matches.length} 个切片</span></div>{retrievalResult.matches.length > 0 && <div className="mt-3 space-y-3">{retrievalResult.matches.map((match) => <article key={match.chunk_id} className="border border-border bg-bg p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-medium text-ink">{match.source_label}</p><Badge variant="success">相似度 {match.similarity}</Badge></div><p className="mt-1 text-xs text-ink-faint">{match.title} · {match.category} · 第 {match.sequence + 1} 个切片{match.source_url ? ` · ${match.source_url}` : ""}</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-ink-muted">{match.excerpt}</p></article>)}</div>}{retrievalResult.requires_human_escalation && <p className="mt-3 text-xs leading-5 text-ink-muted">Agent 遇到同样的未命中结果时会停止猜测，并自动创建人工服务工单。</p>}</div>}
        </CardContent>
      </Card>

      <div className="mb-4 flex flex-wrap items-center gap-2"><form onSubmit={submitSearch} className="flex min-w-[240px] flex-1 items-center gap-2 sm:max-w-xl"><div className="relative min-w-0 flex-1"><Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" /><input value={searchDraft} onChange={(event) => setSearchDraft(event.target.value)} placeholder="搜索标题、来源或知识内容" className="h-10 w-full rounded-md border border-border-strong bg-bg-surface pl-9 pr-3 text-sm text-ink outline-none placeholder:text-ink-faint focus:border-accent" /></div><Button type="submit" variant="secondary" size="sm"><Search className="h-4 w-4" />筛选</Button></form><Button variant="outline" size="icon" onClick={() => void documentsQuery.refetch()} isLoading={documentsQuery.isFetching} aria-label="刷新知识库" title="刷新知识库">{!documentsQuery.isFetching && <RefreshCw className="h-4 w-4" />}</Button></div>

      {documentsQuery.isLoading ? (
        <div className="flex min-h-[40vh] items-center justify-center"><Spinner /></div>
      ) : documentsQuery.isError ? (
        <Card><CardContent className="p-8 text-center text-sm text-danger">知识库加载失败：{getErrorMessage(documentsQuery.error)}</CardContent></Card>
      ) : !data?.documents.length ? (
        <Card><CardContent className="p-10 text-center text-sm text-ink-muted">暂无知识文档，点击“上传知识”添加第一条规则。</CardContent></Card>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border bg-bg-surface shadow-panel">
          <table className="min-w-[980px] w-full border-collapse text-left">
            <thead className="border-b border-border bg-bg-elevated text-xs text-ink-muted">
              <tr>
                <th className="px-4 py-3 font-medium">文档</th>
                <th className="px-4 py-3 font-medium">来源</th>
                <th className="px-4 py-3 font-medium">适用范围</th>
                <th className="px-4 py-3 font-medium">索引</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {data.documents.map((document) => (
                <tr key={document.id} className="border-b border-border align-top last:border-b-0">
                  <td className="max-w-[300px] px-4 py-4">
                    <p className="font-medium text-ink">{document.title}</p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-ink-muted">{document.content_preview}</p>
                    <p className="mt-2 text-[11px] text-ink-faint">{document.category}</p>
                  </td>
                  <td className="max-w-[220px] px-4 py-4 text-xs text-ink-muted">
                    <div className="flex items-center gap-1.5 text-ink">
                      {document.source_type === "WEBPAGE" ? <Link2 className="h-3.5 w-3.5 text-accent" /> : <FileText className="h-3.5 w-3.5 text-accent" />}
                      <span className="truncate">{sourceLabel(document)}</span>
                    </div>
                    <p className="mt-1 text-ink-faint">{document.source_type_label}</p>
                  </td>
                  <td className="px-4 py-4 text-xs text-ink-muted">{scopeLabel(document)}</td>
                  <td className="whitespace-nowrap px-4 py-4 text-xs text-ink-muted">
                    <p>{document.chunk_count} 个切片</p>
                    <p className="mt-1 text-ink-faint">{document.indexed_at ? new Date(document.indexed_at).toLocaleString("zh-CN") : "尚未建立"}</p>
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <Badge variant={STATUS_VARIANT[document.index_status] ?? "accent"}>
                      {statusIcon(document.index_status)}{STATUS_LABEL[document.index_status] ?? document.index_status}
                    </Badge>
                    {document.index_error && <p className="mt-2 max-w-[180px] whitespace-normal text-xs leading-5 text-danger">{document.index_error}</p>}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <div className="flex items-center gap-1">
                      <Button variant="ghost" size="icon" onClick={() => openEditForm(document)} aria-label="编辑文档" title="编辑文档"><Pencil className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => updateMutation.mutate({ documentId: document.id, payload: { is_published: !document.is_published } })} aria-label={document.is_published ? "停用检索" : "启用检索"} title={document.is_published ? "停用检索" : "启用检索"}>{document.is_published ? <CheckCircle2 className="h-4 w-4 text-success" /> : <XCircle className="h-4 w-4 text-ink-faint" />}</Button>
                      <Button variant="ghost" size="icon" onClick={() => reindexMutation.mutate(document.id)} isLoading={reindexMutation.isPending && reindexMutation.variables === document.id} aria-label="重建索引" title="重建索引"><RefreshCw className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" onClick={() => { if (window.confirm(`确定删除“${document.title}”吗？`)) deleteMutation.mutate(document.id); }} aria-label="删除文档" title="删除文档"><Trash2 className="h-4 w-4 text-danger" /></Button>
                    </div>
                    <p className="mt-2 text-[11px] text-ink-faint">{document.is_published ? "Agent 可检索" : "已停用"}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </Container>
  );
}
