import { Link } from "@tanstack/react-router";
import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import {
  ErrorBlock,
  KpiCard,
  LoadingBlock,
  PageHeader,
  Panel,
} from "@/components/app/primitives";
import { formatNumber, formatPct } from "@/lib/format";
import { CloudUpload, Play } from "lucide-react";

export const Route = createFileRoute("/dataset-selection")({
  head: () => ({
    meta: [
      { title: "Dataset Selection — Smart Retry" },
      {
        name: "description",
        content: "Choose a dataset to analyze: try the demo or upload your own CSV.",
      },
    ],
  }),
  component: DatasetSelection,
});

function DatasetSelection() {
  const queryClient = useQueryClient();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => api.uploadAndInfer(file),
    onSuccess: () => queryClient.invalidateQueries({ predicate: (query) =>
      ["dashboard", "business-impact", "recovery-breakdown", "retry-distribution", "confidence", "transactions", "audit"].includes(String(query.queryKey[0]))
    }),
  });

  const demoMutation = useMutation({
    mutationFn: () => api.loadDemoDataset(),
    onSuccess: () => queryClient.invalidateQueries({ predicate: (query) =>
      ["dashboard", "business-impact", "recovery-breakdown", "retry-distribution", "confidence", "transactions", "audit"].includes(String(query.queryKey[0]))
    }),
  });

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".csv")) {
      setValidationError("Only CSV files are accepted");
      return;
    }

    setValidationError(null);
    setSelectedFile(file);
  };

  const handleUpload = () => {
    if (!selectedFile) return;
    uploadMutation.mutate(selectedFile);
  };

  const handleDemo = () => {
    demoMutation.mutate();
  };

  const isProcessing = uploadMutation.isPending || demoMutation.isPending;
  const hasResult = uploadMutation.data || demoMutation.data;

  if (hasResult) {
    const result = uploadMutation.data || demoMutation.data!;
    return (
      <div className="space-y-8">
        <PageHeader
          eyebrow="Inference results"
          title={result.dataset_source === "demo" ? "Demo dataset loaded" : "CSV uploaded and processed"}
          description={
            result.dataset_source === "demo"
              ? `Processed ${formatNumber(result.total_records)} synthetic evaluation records`
              : `Processed ${formatNumber(result.total_records)} rows from your CSV`
          }
        />

        <Panel
          title="Dataset Information"
          description={result.dataset_source === "demo" ? "Demo synthetic evaluation data" : "Uploaded CSV"}
        >
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Data source:</span>
              <span className="font-medium">
                {result.dataset_source === "demo" ? "Demo synthetic evaluation dataset" : "Uploaded CSV"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Total records:</span>
              <span className="font-medium">{formatNumber(result.total_records)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Records processed:</span>
              <span className="font-medium">{formatNumber(result.processed_records)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Failed records:</span>
              <span className={result.failed_records > 0 ? "font-medium text-red-600" : "font-medium"}>
                {formatNumber(result.failed_records)}
              </span>
            </div>
          </div>
        </Panel>

        <div className="grid gap-4 sm:grid-cols-3">
          <KpiCard
            label="Eligible for retry"
            value={formatNumber(result.eligible_records)}
            sub={`${formatPct((result.eligible_records / result.processed_records) * 100, 1)} of records`}
            tone="mint"
          />
          <KpiCard
            label="High confidence"
            value={formatNumber(result.eligible_by_confidence?.["High"] ?? 0)}
            sub="Recommended for retry"
            tone="lavender"
          />
          <KpiCard
            label="Avg retry timing"
            value={`${(result.avg_selected_retry_hours ?? 0).toFixed(1)}h`}
            sub="Mean selected offset"
            tone="sky"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <Panel title="Medium confidence">
            <div className="text-3xl font-bold">
              {formatNumber(result.eligible_by_confidence?.["Medium"] ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Records in medium tier</p>
          </Panel>
          <Panel title="Low confidence">
            <div className="text-3xl font-bold">
              {formatNumber(result.eligible_by_confidence?.["Low"] ?? 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">Stopped by policy</p>
          </Panel>
          <Panel title="Errors">
            <div className={`text-3xl font-bold ${result.errors.length > 0 ? "text-red-600" : ""}`}>
              {result.errors.length}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {result.errors.length > 0 ? "See errors below" : "No errors"}
            </p>
          </Panel>
        </div>

        {result.errors.length > 0 && (
          <Panel title="Errors">
            <div className="space-y-2">
              {result.errors.map((err, i) => (
                <div key={i} className="text-sm text-red-600 bg-red-50 p-2 rounded">
                  {err}
                </div>
              ))}
            </div>
          </Panel>
        )}

        <div className="flex gap-4">
  <Link
    to="/"
    className="px-4 py-2 bg-primary text-primary-foreground rounded-lg font-medium hover:bg-primary/90"
  >
    View Dashboard
  </Link>

  <button
    onClick={() => {
      uploadMutation.reset();
      demoMutation.reset();
      setSelectedFile(null);
    }}
    className="px-4 py-2 border border-border rounded-lg font-medium hover:bg-accent"
  >
    Select Different Dataset
  </button>
</div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Get started"
        title="Select your dataset"
        description="Try the demo dataset or upload your own CSV of failed payments for analysis and retry optimization recommendations."
      />

      <div className="grid gap-6 sm:grid-cols-2">
        {/* Demo Dataset Card */}
        <Panel
          title="Try Demo Dataset"
          description="Use our synthetic evaluation dataset (100k failed payments) to see Smart Retry in action."
        >
          <div className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Records:</span>
                <span className="font-medium">100,000 transactions</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Type:</span>
                <span className="font-medium">Synthetic evaluation data</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Model:</span>
                <span className="font-medium">Existing trained model</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Retrain:</span>
                <span className="font-medium text-green-600">No</span>
              </div>
            </div>

            <button
              onClick={handleDemo}
              disabled={isProcessing}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-mint text-white rounded-lg font-medium hover:bg-mint/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {demoMutation.isPending ? (
                <>
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <Play size={18} />
                  <span>Load Demo Dataset</span>
                </>
              )}
            </button>

            {demoMutation.isError && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                {demoMutation.error instanceof Error
                  ? demoMutation.error.message
                  : "Failed to load demo dataset"}
              </div>
            )}
          </div>
        </Panel>

        {/* CSV Upload Card */}
        <Panel
          title="Upload CSV"
          description="Upload your own CSV file with failed payment data for Smart Retry analysis."
        >
          <div className="space-y-4">
            <div className="space-y-2 text-sm">
              <div className="font-medium">Required columns:</div>
              <ul className="text-xs text-muted-foreground space-y-1">
                <li>• amount_inr</li>
                <li>• decline_reason</li>
                <li>• payment_method</li>
                <li>• hour_of_day, day_of_month, day_of_week</li>
                <li>• customer_previous_success_rate</li>
                <li>• customer_previous_failure_count</li>
                <li>• days_since_last_successful_payment</li>
              </ul>
            </div>

            <div className="border-2 border-dashed border-border rounded-lg p-6 text-center">
              <input
                type="file"
                accept=".csv"
                onChange={handleFileSelect}
                disabled={isProcessing}
                className="hidden"
                id="csv-upload"
              />
              <label
                htmlFor="csv-upload"
                className="cursor-pointer flex flex-col items-center gap-2"
              >
                <CloudUpload size={32} className="text-muted-foreground" />
                <span className="text-sm font-medium">
                  {selectedFile ? selectedFile.name : "Click to select CSV or drag and drop"}
                </span>
                <span className="text-xs text-muted-foreground">CSV files only</span>
              </label>
            </div>

            {validationError && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">{validationError}</div>
            )}

            <button
              onClick={handleUpload}
              disabled={!selectedFile || isProcessing}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-peach text-white rounded-lg font-medium hover:bg-peach/90 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadMutation.isPending ? (
                <>
                  <span>Uploading...</span>
                </>
              ) : (
                <>
                  <CloudUpload size={18} />
                  <span>Upload and Analyze</span>
                </>
              )}
            </button>

            {uploadMutation.isError && (
              <div className="text-sm text-red-600 bg-red-50 p-2 rounded">
                {uploadMutation.error instanceof Error
                  ? uploadMutation.error.message
                  : "Failed to upload CSV"}
              </div>
            )}
          </div>
        </Panel>
      </div>

      {isProcessing && <LoadingBlock rows={4} />}
    </div>
  );
}
