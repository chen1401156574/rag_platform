import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Save, RotateCcw, SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import type { SystemSettings } from "@/services/settingsService";
import { getSystemSettings, saveSystemSettings } from "@/services/settingsService";
import { getErrorMessage } from "@/utils/error";

function InfoItem({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-slate-200/70 bg-white px-4 py-3">
      <span className="text-xs text-slate-500">{label}</span>
      <div className="text-sm font-medium text-slate-800">{value}</div>
    </div>
  );
}

export function SystemSettingsPage() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // Editable fields
  const [temperature, setTemperature] = useState(0.7);
  const [topK, setTopK] = useState(5);
  const [vectorSimilarityWeight, setVectorSimilarityWeight] = useState(0.6);
  const [similarityThreshold, setSimilarityThreshold] = useState(0.1);
  const [candidateTop, setCandidateTop] = useState(1024);
  const [rerankEnabled, setRerankEnabled] = useState(true);
  const [promptTemplate, setPromptTemplate] = useState("");
  const [defaultChatModel, setDefaultChatModel] = useState("");
  const [queryRewriteEnabled, setQueryRewriteEnabled] = useState(false);
  const [rateLimitEnabled, setRateLimitEnabled] = useState(false);
  const [maxConcurrent, setMaxConcurrent] = useState(4);
  const [historyKeepTurns, setHistoryKeepTurns] = useState(10);

  const loadSettings = async () => {
    try {
      setLoading(true);
      const data = await getSystemSettings();
      setSettings(data);
      // Populate editable fields from loaded data
      const t = data?.rag?.generation?.temperature;
      setTemperature(typeof t === "number" ? t : 0.7);
      const k = data?.rag?.retrieval?.topK;
      setTopK(typeof k === "number" ? k : 5);
      setVectorSimilarityWeight(data?.rag?.retrieval?.vectorSimilarityWeight ?? 0.6);
      setSimilarityThreshold(data?.rag?.retrieval?.similarityThreshold ?? 0.1);
      setCandidateTop(data?.rag?.retrieval?.candidateTop ?? 1024);
      setRerankEnabled(data?.rag?.retrieval?.rerankEnabled ?? true);
      setPromptTemplate(data?.rag?.generation?.promptTemplate || "");
      setDefaultChatModel(data?.ai?.chat?.defaultModel || "");
      setQueryRewriteEnabled(!!data?.rag?.queryRewrite?.enabled);
      setRateLimitEnabled(!!data?.rag?.rateLimit?.global?.enabled);
      setMaxConcurrent(data?.rag?.rateLimit?.global?.maxConcurrent ?? 4);
      setHistoryKeepTurns(data?.rag?.memory?.historyKeepTurns ?? 10);
    } catch (error) {
      toast.error(getErrorMessage(error, "加载系统配置失败"));
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSettings();
  }, []);

  const handleSave = async () => {
    // Build the patch following backend expected structure
    const patch = {
      rag: {
        retrieval: {
          topK,
          vectorSimilarityWeight,
          similarityThreshold,
          candidateTop,
          rerankEnabled,
        },
        generation: { temperature, promptTemplate },
        queryRewrite: { enabled: queryRewriteEnabled },
        rateLimit: {
          global: {
            enabled: rateLimitEnabled,
            maxConcurrent,
          },
        },
        memory: { historyKeepTurns },
      },
      ai: {
        chat: { defaultModel: defaultChatModel || undefined },
      },
    };

    setSaving(true);
    try {
      const updated = await saveSystemSettings(patch);
      setSettings(updated);
      toast.success("系统配置已保存");
    } catch (error) {
      toast.error(getErrorMessage(error, "保存配置失败"));
      console.error(error);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (!settings) return;
    setTemperature(settings?.rag?.generation?.temperature ?? 0.7);
    setTopK(settings?.rag?.retrieval?.topK ?? 5);
    setVectorSimilarityWeight(settings?.rag?.retrieval?.vectorSimilarityWeight ?? 0.6);
    setSimilarityThreshold(settings?.rag?.retrieval?.similarityThreshold ?? 0.1);
    setCandidateTop(settings?.rag?.retrieval?.candidateTop ?? 1024);
    setRerankEnabled(settings?.rag?.retrieval?.rerankEnabled ?? true);
    setPromptTemplate(settings?.rag?.generation?.promptTemplate ?? "");
    setDefaultChatModel(settings?.ai?.chat?.defaultModel ?? "");
    setQueryRewriteEnabled(!!settings?.rag?.queryRewrite?.enabled);
    setRateLimitEnabled(!!settings?.rag?.rateLimit?.global?.enabled);
    setMaxConcurrent(settings?.rag?.rateLimit?.global?.maxConcurrent ?? 4);
    setHistoryKeepTurns(settings?.rag?.memory?.historyKeepTurns ?? 10);
    toast.info("已恢复为上次保存的值");
  };

  if (loading) {
    return (
      <div className="admin-page">
        <div className="text-sm text-muted-foreground">加载中...</div>
      </div>
    );
  }

  if (!settings) {
    return (
      <div className="admin-page">
        <div className="text-sm text-muted-foreground">暂无可展示的配置</div>
      </div>
    );
  }

  const { rag, ai } = settings;
  const providers = Object.entries(ai.providers || {});
  const chatCandidates = ai.chat.candidates || [];
  const ragDefault = rag.default || {
    collectionName: "-",
    dimension: 0,
    metricType: "-",
  };
  const aiSelection = ai.selection || {
    failureThreshold: "-",
    openDurationMs: "-",
  };
  const aiStream = ai.stream || {
    messageChunkSize: "-",
  };
  const embedding = ai.embedding || { defaultModel: "-", candidates: [] };
  const rerank = ai.rerank || { defaultModel: "-", candidates: [] };

  return (
    <div className="admin-page">
      <div className="admin-page-header">
        <div>
          <h1 className="admin-page-title">系统配置</h1>
          <p className="admin-page-subtitle">调整全局 RAG 检索与大模型参数，保存后实时生效</p>
        </div>
        <div className="admin-page-actions">
          <Button variant="outline" onClick={handleReset} disabled={saving}>
            <RotateCcw className="w-4 h-4 mr-2" />
            重置
          </Button>
          <Button className="admin-primary-gradient" onClick={handleSave} disabled={saving}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? "保存中..." : "保存配置"}
          </Button>
        </div>
      </div>

      {/* ── RAG 检索与生成参数 ── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <SlidersHorizontal className="w-5 h-5" />
            RAG 检索与生成参数
          </CardTitle>
          <CardDescription>调整召回、重排、大模型温度与提示词模板</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Temperature（温度）</Label>
                <span className="text-sm font-medium tabular-nums text-slate-700">{temperature.toFixed(1)}</span>
              </div>
              <Slider
                value={[temperature]}
                onValueChange={(v) => setTemperature(v[0])}
                min={0}
                max={2}
                step={0.1}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0 — 更确定</span>
                <span>2 — 更随机</span>
              </div>
            </div>
            <div className="space-y-2">
              <Label>默认 TopK 检索数量</Label>
              <Input
                type="number"
                min={1}
                max={50}
                value={topK}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (v >= 1 && v <= 50) setTopK(v);
                }}
              />
              <p className="text-xs text-muted-foreground">每次问答返回的相关文档片段数（1-50）</p>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>向量相似度权重</Label>
                <span className="text-sm font-medium tabular-nums text-slate-700">
                  {vectorSimilarityWeight.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[vectorSimilarityWeight]}
                onValueChange={(v) => setVectorSimilarityWeight(v[0])}
                min={0}
                max={1}
                step={0.05}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>0 — 更偏关键词</span>
                <span>1 — 更偏向量</span>
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>相似度阈值</Label>
                <span className="text-sm font-medium tabular-nums text-slate-700">
                  {similarityThreshold.toFixed(2)}
                </span>
              </div>
              <Slider
                value={[similarityThreshold]}
                onValueChange={(v) => setSimilarityThreshold(v[0])}
                min={0}
                max={1}
                step={0.05}
                className="w-full"
              />
              <p className="text-xs text-muted-foreground">低于阈值的候选片段会被过滤</p>
            </div>
            <div className="space-y-2">
              <Label>候选召回上限</Label>
              <Input
                type="number"
                min={1}
                max={4096}
                value={candidateTop}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (v >= 1 && v <= 4096) setCandidateTop(v);
                }}
              />
              <p className="text-xs text-muted-foreground">进入排序阶段的最大候选数量（1-4096）</p>
            </div>
            <div className="flex min-h-[76px] items-center justify-between rounded-lg border border-slate-200/70 bg-white px-4 py-3">
              <div className="space-y-1">
                <Label>启用模型重排</Label>
                <p className="text-xs text-muted-foreground">开启后使用配置的 rerank 模型参与排序</p>
              </div>
              <Switch checked={rerankEnabled} onCheckedChange={setRerankEnabled} />
            </div>
          </div>

          <div className="space-y-2">
            <Label>RAG 提示词模板</Label>
            <Textarea
              value={promptTemplate}
              onChange={(e) => setPromptTemplate(e.target.value)}
              rows={4}
              placeholder="请基于给定文档内容回答用户问题..."
              className="font-mono text-sm"
            />
            <p className="text-xs text-muted-foreground">
              使用 {"{question}"} 作为用户问题的占位符。保存后新对话立即生效。
            </p>
          </div>

          <div className="space-y-2">
            <Label>默认对话模型</Label>
            <Select value={defaultChatModel} onValueChange={setDefaultChatModel}>
              <SelectTrigger className="w-[320px]">
                <SelectValue placeholder="选择默认模型" />
              </SelectTrigger>
              <SelectContent>
                {chatCandidates
                  .filter((c) => c.enabled !== false)
                  .map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.id} ({c.provider})
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* ── 策略开关 ── */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>查询改写</CardTitle>
            <CardDescription>历史上下文压缩与多轮改写</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <Label>启用查询改写</Label>
              <Switch checked={queryRewriteEnabled} onCheckedChange={setQueryRewriteEnabled} />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>全局限流</CardTitle>
            <CardDescription>并发访问控制</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <Label>启用来宾限流</Label>
              <Switch checked={rateLimitEnabled} onCheckedChange={setRateLimitEnabled} />
            </div>
            {rateLimitEnabled && (
              <div className="space-y-2">
                <Label>最大并发数</Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={maxConcurrent}
                  onChange={(e) => {
                    const v = parseInt(e.target.value, 10);
                    if (v >= 1 && v <= 20) setMaxConcurrent(v);
                  }}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── 记忆管理 ── */}
      <Card>
        <CardHeader>
          <CardTitle>记忆管理</CardTitle>
          <CardDescription>对话历史保留与摘要策略</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-2">
              <Label>保留对话轮数</Label>
              <Input
                type="number"
                min={1}
                max={50}
                value={historyKeepTurns}
                onChange={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (v >= 1 && v <= 50) setHistoryKeepTurns(v);
                }}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ── 只读信息卡片 ── */}
      <Card>
        <CardHeader>
          <CardTitle>RAG 默认配置</CardTitle>
          <CardDescription>向量空间与检索基础参数（只读）</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <InfoItem label="Collection" value={ragDefault.collectionName} />
          <InfoItem label="Dimension" value={ragDefault.dimension} />
          <InfoItem label="Metric Type" value={ragDefault.metricType} />
        </CardContent>
      </Card>

      {/* ── 模型服务提供方 ── */}
      <Card>
        <CardHeader>
          <CardTitle>模型服务提供方</CardTitle>
          <CardDescription>接入地址与端点配置（只读）</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="min-w-[760px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[140px]">Provider</TableHead>
                <TableHead className="w-[240px]">URL</TableHead>
                <TableHead className="w-[200px]">API Key</TableHead>
                <TableHead>Endpoints</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {providers.map(([name, provider]) => (
                <TableRow key={name}>
                  <TableCell className="font-medium">{name}</TableCell>
                  <TableCell>{provider.url}</TableCell>
                  <TableCell>{provider.apiKey ? provider.apiKey : "-"}</TableCell>
                  <TableCell>
                    <div className="space-y-1 text-xs text-muted-foreground">
                      {Object.entries(provider.endpoints).map(([key, value]) => (
                        <div key={key}>
                          {key}: {value}
                        </div>
                      ))}
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ── 模型选择策略 ── */}
      <Card>
        <CardHeader>
          <CardTitle>模型选择策略</CardTitle>
          <CardDescription>熔断与选择阈值（只读）</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <InfoItem label="Failure Threshold" value={aiSelection.failureThreshold} />
          <InfoItem label="Open Duration (ms)" value={aiSelection.openDurationMs} />
        </CardContent>
      </Card>

      {/* ── 流式响应 ── */}
      <Card>
        <CardHeader>
          <CardTitle>流式响应</CardTitle>
          <CardDescription>输出分片大小（只读）</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <InfoItem label="Message Chunk Size" value={aiStream.messageChunkSize} />
        </CardContent>
      </Card>

      {/* ── Chat 模型候选列表 ── */}
      <Card>
        <CardHeader>
          <CardTitle>Chat 模型候选列表</CardTitle>
          <CardDescription>可用对话模型（只读）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoItem label="Default Model" value={ai.chat.defaultModel} />
            <InfoItem label="Deep Thinking Model" value={ai.chat.deepThinkingModel} />
          </div>
          <Table className="min-w-[720px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[220px]">ID</TableHead>
                <TableHead className="w-[120px]">Provider</TableHead>
                <TableHead className="w-[200px]">Model</TableHead>
                <TableHead className="w-[100px]">Thinking</TableHead>
                <TableHead className="w-[90px]">Priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {chatCandidates.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.id}</TableCell>
                  <TableCell>{item.provider}</TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell>{item.supportsThinking ? "支持" : "-"}</TableCell>
                  <TableCell>{item.priority}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ── Embedding 模型 ── */}
      <Card>
        <CardHeader>
          <CardTitle>Embedding 模型配置</CardTitle>
          <CardDescription>向量化模型列表（只读）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoItem label="Default Model" value={embedding.defaultModel} />
          </div>
          <Table className="min-w-[720px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[220px]">ID</TableHead>
                <TableHead className="w-[120px]">Provider</TableHead>
                <TableHead className="w-[200px]">Model</TableHead>
                <TableHead className="w-[110px]">Dimension</TableHead>
                <TableHead className="w-[90px]">Priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {embedding.candidates.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.id}</TableCell>
                  <TableCell>{item.provider}</TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell>{item.dimension}</TableCell>
                  <TableCell>{item.priority}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ── Rerank 模型 ── */}
      <Card>
        <CardHeader>
          <CardTitle>Rerank 模型配置</CardTitle>
          <CardDescription>重排模型列表（只读）</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <InfoItem label="Default Model" value={rerank.defaultModel} />
          </div>
          <Table className="min-w-[640px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-[220px]">ID</TableHead>
                <TableHead className="w-[120px]">Provider</TableHead>
                <TableHead className="w-[200px]">Model</TableHead>
                <TableHead className="w-[90px]">Priority</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rerank.candidates.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">{item.id}</TableCell>
                  <TableCell>{item.provider}</TableCell>
                  <TableCell>{item.model}</TableCell>
                  <TableCell>{item.priority}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
