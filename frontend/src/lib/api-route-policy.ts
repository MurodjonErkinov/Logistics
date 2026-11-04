const routes = [
  /^auth\/(login|register|registration-code|password-reset-code|reset-password|logout|me|users(?:\/\d+)?)$/,
  /^cargo\/(cities|loads(?:\/\d+(?:\/(?:claim|map-locations))?)?)$/,
  /^driver\/vehicles(?:\/\d+)?$/,
  /^driver\/tickets(?:\/simple|\/\d+(?:\/(?:return-trip|simple))?)?$/,
  /^driver\/notifications(?:\/(?:unread|read-all|\d+(?:\/(?:read|dismiss))?))?$/,
  /^driver\/preferences$/,
  /^partners\/(?:companies(?:\/\d+(?:\/members(?:\/\d+)?)?)?|invitations(?:\/\d+(?:\/accept)?)?)$/,
];

export function isAllowedApiRoute(route: string) {
  return routes.some((pattern) => pattern.test(route));
}
