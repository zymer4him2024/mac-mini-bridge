import { httpsCallable } from "firebase/functions";

import { getFirebaseFunctions } from "@/lib/firebase/client";

interface DeleteAccountResponse {
  success: boolean;
}

export async function callDeleteAccount(): Promise<void> {
  const callable = httpsCallable<unknown, DeleteAccountResponse>(
    getFirebaseFunctions(),
    "deleteAccount",
  );
  const result = await callable({});
  if (!result.data?.success) {
    throw new Error("deleteAccount: function returned failure");
  }
}
