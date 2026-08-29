import { defineRailway, github, project, service } from "railway/iac";

export const partial = "worker";

export default defineRailway(() => {
  const worker = service("worker", {
    source: github("thinkelearn/thinkelearn", { branch: "main" }),
    build: {
      builder: "RAILPACK",
    },
    deploy: {
      runtime: "V2",
      numReplicas: 1,
      startCommand:
        "DJANGO_SETTINGS_MODULE=thinkelearn.settings.production celery -A thinkelearn worker --loglevel=info",
      restartPolicyType: "ON_FAILURE",
      restartPolicyMaxRetries: 10,
    },
  });

  return project("thinkelearn", {
    resources: [worker],
  });
});
