/**
 * Cloud Functions for Shomery.
 *
 * deleteAccount: cascade-deletes everything Shomery owns for the calling user
 * — Firestore docs under users/{uid}/**, Storage objects under
 * summaries/{uid}/** and pdfs/{uid}/**, and the Firebase Auth user record.
 * Required because the web client cannot drop subcollections or delete its own
 * auth user without admin-SDK access.
 */

const {onCall, HttpsError} = require("firebase-functions/https");
const {setGlobalOptions} = require("firebase-functions");
const {initializeApp} = require("firebase-admin/app");
const {getFirestore} = require("firebase-admin/firestore");
const {getStorage} = require("firebase-admin/storage");
const {getAuth} = require("firebase-admin/auth");
const logger = require("firebase-functions/logger");

initializeApp();
setGlobalOptions({maxInstances: 10});

exports.deleteAccount = onCall(async (request) => {
  const uid = request.auth && request.auth.uid;
  if (!uid) {
    throw new HttpsError(
        "unauthenticated",
        "Must be signed in to delete your account.",
    );
  }

  logger.info("deleteAccount: starting cascade", {uid});

  const db = getFirestore();
  const bucket = getStorage().bucket();

  await db.recursiveDelete(db.doc(`users/${uid}`));

  await Promise.all([
    bucket.deleteFiles({prefix: `summaries/${uid}/`}).catch((err) => {
      logger.warn("deleteAccount: storage prefix delete failed", {
        uid,
        prefix: `summaries/${uid}/`,
        message: err && err.message,
      });
    }),
    bucket.deleteFiles({prefix: `pdfs/${uid}/`}).catch((err) => {
      logger.warn("deleteAccount: storage prefix delete failed", {
        uid,
        prefix: `pdfs/${uid}/`,
        message: err && err.message,
      });
    }),
  ]);

  await getAuth().deleteUser(uid);

  logger.info("deleteAccount: complete", {uid});
  return {success: true};
});
