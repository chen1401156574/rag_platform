import { useEffect, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { createKnowledgeBase } from "@/services/knowledgeService";
import { getErrorMessage } from "@/utils/error";

export function CreateKnowledgeBaseDialog({
  open,
  onOpenChange,
  onSuccess
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: () => void;
}) {
  const [name, setName] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) {
      setName("");
      setEmbeddingModel("");
    }
  }, [open]);

  const handleSubmit = async () => {
    const trimmedName = name.trim();
    if (!trimmedName) {
      toast.error("Knowledge base name is required");
      return;
    }
    setSubmitting(true);
    try {
      await createKnowledgeBase({
        name: trimmedName,
        embeddingModel: embeddingModel.trim() || undefined
      });
      toast.success("Knowledge base created");
      onOpenChange(false);
      onSuccess?.();
    } catch (error) {
      toast.error(getErrorMessage(error, "Create knowledge base failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create knowledge base</DialogTitle>
          <DialogDescription>Create a global knowledge base for the admin console.</DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <label className="space-y-2 text-sm font-medium">
            <span>Name</span>
            <Input value={name} onChange={(event) => setName(event.target.value)} autoFocus />
          </label>
          <label className="space-y-2 text-sm font-medium">
            <span>Embedding model</span>
            <Input
              value={embeddingModel}
              onChange={(event) => setEmbeddingModel(event.target.value)}
              placeholder="Use backend default"
            />
          </label>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            Create
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
