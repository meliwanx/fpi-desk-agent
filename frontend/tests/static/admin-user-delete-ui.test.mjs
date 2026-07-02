import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const adminApp = readFileSync(
  new URL("../../../admin-frontend/src/App.tsx", import.meta.url),
  "utf8",
);
const adminApi = readFileSync(
  new URL("../../../backend/app/api/admin.py", import.meta.url),
  "utf8",
);
const companyStore = readFileSync(
  new URL("../../../backend/app/company_auth/store.py", import.meta.url),
  "utf8",
);

assert.match(adminApp, /async function deleteUser/, "admin users page should implement employee deletion");
assert.match(adminApp, /method:\s*"DELETE"/, "admin users page should call a DELETE endpoint");
assert.match(adminApp, /删除员工/, "admin users table should expose a delete employee action");
assert.match(adminApp, /confirm\(/, "admin user deletion should require browser confirmation");

assert.match(adminApi, /@router\.delete\("\/admin\/users\/\{user_id\}"/, "admin API should expose a user delete endpoint");
assert.match(adminApi, /delete_company_user/, "admin API should audit employee deletion");
assert.match(adminApi, /Cannot delete yourself/, "admin API should prevent admins from deleting their own account");

assert.match(companyStore, /deleted_at/, "company auth store should track soft-deleted employees");
assert.match(companyStore, /async def delete_user/, "company auth store should implement soft deletion");
assert.match(companyStore, /deleted_at\.is_\(None\)/, "company auth user lists should hide soft-deleted employees");
