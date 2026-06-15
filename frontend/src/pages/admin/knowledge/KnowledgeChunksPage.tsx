import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, ChevronLeft, ChevronRight, CircleHelp, RefreshCw, Search } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { RelativeTime } from "@/components/RelativeTime";

import type {
  KnowledgeChunk,
  KnowledgeDocument,
  PageResult,
  RetrievalTestResult
} from "@/services/knowledgeService";
import {
  getChunksPage,
  getDocument,
  getKnowledgeBase,
  testDocumentRetrieval
} from "@/services/knowledgeService";
import { getErrorMessage } from "@/utils/error";

const PAGE_SIZE = 10;

const truncateText = (value?: string | null, max = 180) => {
  if (!value) return "-";
  if (value.length <= max) return value;
  return `${value.slice(0, max)}...`;
};

const enabledLabel = (enabled?: number | null) => (enabled === 0 ? "禁用" : "启用");

const formatScore = (value?: number | null) => {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toFixed(4);
};

export function KnowledgeChunksPage() {
  const { kbId, docId } = useParams();
  const navigate = useNavigate();
  const [doc, setDoc] = useState<KnowledgeDocument | null>(null);
  const [kbName, setKbName] = useState("");
  const [pageData, setPageData] = useState<PageResult<KnowledgeChunk> | null>(null);
  const [pageNo, setPageNo] = useState(1);
  const [loading, setLoading] = useState(false);
  const [enabledFilter, setEnabledFilter] = useState<number | undefined>();
  const [question, setQuestion] = useState("");
  const [topK, setTopK] = useState("5");
  const [testing, setTesting] = useState(false);
  const [retrievalResult, setRetrievalResult] = useState<RetrievalTestResult | null>(null);

  const chunks = pageData?.records || [];

  const loadDocument = useCallback(async () => {
    if (!docId) return;
    try {
      const data = await getDocument(docId);
      setDoc(data);
    } catch (error) {
      toast.error(getErrorMessage(error, "加载文档失败"));
      console.error(error);
    }
  }, [docId]);

  const loadChunks = useCallback(async (current = pageNo, enabled = enabledFilter) => {
    if (!docId) return;
    setLoading(true);
    try {
      const data = await getChunksPage(docId, {
        current,
        size: PAGE_SIZE,
        enabled
      });
      setPageData(data);
    } catch (error) {
      toast.error(getErrorMessage(error, "加载分块失败"));
      console.error(error);
    } finally {
      setLoading(false);
    }
  }, [docId, enabledFilter, pageNo]);

  useEffect(() => {
    void loadDocument();
  }, [loadDocument]);

  useEffect(() => {
    if (!kbId) return;
    getKnowledgeBase(kbId).then((kb) => setKbName(kb.name)).catch(() => {});
  }, [kbId]);

  useEffect(() => {
    void loadChunks();
  }, [loadChunks]);

  useEffect(() => {
    setRetrievalResult(null);
  }, [docId]);

  const handleRetrievalTest = async () => {
    if (!docId) return;
    const trimmed = question.trim();
    if (!trimmed) {
      toast.error("请输入测试问题");
      return;
    }

    const parsedTopK = Number(topK);
    if (!Number.isInteger(parsedTopK) || parsedTopK < 1 || parsedTopK > 50) {
      toast.error("TopK 必须是 1 到 50 的整数");
      return;
    }

    setTesting(true);
    try {
      const data = await testDocumentRetrieval(docId, {
        question: trimmed,
        topK: parsedTopK
      });
      setRetrievalResult(data);
      if (!data.records?.length) {
        toast.info("当前文档未命中 Chunk");
      }
    } catch (error) {
      toast.error(getErrorMessage(error, "相似度测试失败"));
      console.error(error);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">Chunk 查看与召回测试</h1>
          <p className="admin-page-subtitle">
            {doc?.docName || docId} {kbName ? `（知识库: ${kbName}）` : ""}
          </p>
        </div>
        <div className="admin-page-actions">
          <Button variant="outline" onClick={() => navigate(`/admin/knowledge/${kbId}`)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            返回文档
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>相似度测试</CardTitle>
          <CardDescription>当前文档范围内的 TopK 召回结果</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-[1fr_120px_auto] lg:items-end">
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="retrieval-question">测试问题</label>
              <Textarea
                id="retrieval-question"
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="输入一个用于验证当前文档召回质量的问题"
                className="min-h-[88px] resize-none"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="retrieval-topk">TopK</label>
              <Input
                id="retrieval-topk"
                type="number"
                min={1}
                max={50}
                step={1}
                value={topK}
                onChange={(event) => setTopK(event.target.value)}
              />
            </div>
            <Button className="admin-primary-gradient" onClick={handleRetrievalTest} disabled={testing}>
              <Search className="mr-2 h-4 w-4" />
              {testing ? "测试中..." : "测试召回"}
            </Button>
          </div>

          {retrievalResult ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                <span>ES Doc ID</span>
                <span className="rounded bg-muted px-2 py-1 font-mono text-xs text-foreground break-all">
                  {retrievalResult.esDocId}
                </span>
                <span>Collection</span>
                <span className="rounded bg-muted px-2 py-1 font-mono text-xs text-foreground">
                  {retrievalResult.collectionName}
                </span>
              </div>
              {retrievalResult.records.length === 0 ? (
                <div className="py-6 text-center text-muted-foreground">暂无命中结果</div>
              ) : (
                <Table className="min-w-[980px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-[70px]">排名</TableHead>
                      <TableHead className="w-[90px]">综合分</TableHead>
                      <TableHead className="w-[90px]">向量分</TableHead>
                      <TableHead className="w-[90px]">词项分</TableHead>
                      <TableHead>命中内容</TableHead>
                      <TableHead className="w-[180px]">ES Chunk ID</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {retrievalResult.records.map((item) => (
                      <TableRow key={`${item.chunkId}-${item.rank}`}>
                        <TableCell>
                          <Badge variant="outline">#{item.rank}</Badge>
                        </TableCell>
                        <TableCell>{formatScore(item.score ?? item.similarity)}</TableCell>
                        <TableCell>{formatScore(item.vectorSimilarity)}</TableCell>
                        <TableCell>{formatScore(item.termSimilarity)}</TableCell>
                        <TableCell className="max-w-[420px] break-all text-sm text-muted-foreground">
                          {truncateText(item.highlight || item.content, 220)}
                        </TableCell>
                        <TableCell className="break-all font-mono text-xs">{item.chunkId || "-"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Chunk 列表</CardTitle>
              <CardDescription>Elasticsearch 中的真实写入内容</CardDescription>
            </div>
            <div className="flex flex-1 flex-wrap items-center justify-end gap-2">
              <Select
                value={enabledFilter === undefined ? "all" : String(enabledFilter)}
                onValueChange={(value) => {
                  setPageNo(1);
                  setEnabledFilter(value === "all" ? undefined : Number(value));
                }}
              >
                <SelectTrigger className="w-[160px]">
                  <SelectValue placeholder="启用状态" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">全部状态</SelectItem>
                  <SelectItem value="1">启用</SelectItem>
                  <SelectItem value="0">禁用</SelectItem>
                </SelectContent>
              </Select>
              <Button
                variant="outline"
                onClick={() => {
                  setPageNo(1);
                  void loadChunks(1, enabledFilter);
                }}
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                刷新
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-8 text-center text-muted-foreground">加载中...</div>
          ) : chunks.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground">暂无分块</div>
          ) : (
            <Table className="min-w-[1020px]">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[70px]">序号</TableHead>
                  <TableHead>内容摘要</TableHead>
                  <TableHead className="w-[90px]">状态</TableHead>
                  <TableHead className="w-[90px]">字符数</TableHead>
                  <TableHead className="w-[90px]">
                    <span className="inline-flex items-center gap-1">
                      Token
                      <TooltipProvider delayDuration={0}>
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <CircleHelp className="h-3.5 w-3.5 text-muted-foreground" />
                          </TooltipTrigger>
                          <TooltipContent side="top">
                            <span className="text-xs font-normal">预估 Token 数</span>
                          </TooltipContent>
                        </Tooltip>
                      </TooltipProvider>
                    </span>
                  </TableHead>
                  <TableHead className="w-[190px]">ES Chunk ID</TableHead>
                  <TableHead className="w-[170px]">创建时间</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {chunks.map((chunk) => (
                  <TableRow key={chunk.id}>
                    <TableCell>{chunk.chunkIndex ?? "-"}</TableCell>
                    <TableCell className="max-w-[460px] break-all text-sm text-muted-foreground">
                      {truncateText(chunk.content)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={chunk.enabled === 0 ? "outline" : "default"}>
                        {enabledLabel(chunk.enabled)}
                      </Badge>
                    </TableCell>
                    <TableCell>{chunk.charCount ?? "-"}</TableCell>
                    <TableCell>{chunk.tokenCount ?? "-"}</TableCell>
                    <TableCell className="break-all font-mono text-xs">{chunk.id}</TableCell>
                    <TableCell><RelativeTime value={chunk.createTime || chunk.updateTime} /></TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}

          {pageData ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-500">
              <span>共 {pageData.total} 条</span>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPageNo((prev) => Math.max(1, prev - 1))}
                  disabled={pageData.current <= 1}
                >
                  <ChevronLeft className="mr-1 h-4 w-4" />
                  上一页
                </Button>
                <span>
                  {pageData.current} / {pageData.pages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPageNo((prev) => Math.min(pageData.pages || 1, prev + 1))}
                  disabled={pageData.current >= pageData.pages}
                >
                  下一页
                  <ChevronRight className="ml-1 h-4 w-4" />
                </Button>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
