using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using Google.Cloud.PubSub.V1;

namespace IapEmulatorDemo;

/// <summary>
/// Simple demonstration of Google Play IAP Emulator usage from .NET, now organized with a command pattern per step.
/// </summary>
class Program
{
    private const string EmulatorBaseUrl = "http://localhost:8080";
    private const string PackageName = "com.example.app";
    private const string SubscriptionId = "premium.personal.yearly";

    private const string PubSubProjectId = "emulator-project";
    private const string PubSubSubscription = "iap_rtdn_sub";

    static async Task Main(string[] args)
    {
        PrintBanner("Google Play IAP Emulator - .NET Demo");

        if (args.Length > 0 && args[0] == "listen")
        {
            await RunRtdnListenerDemo();
        }
        else
        {
            await RunApiDemo();
            Console.WriteLine("\nTo listen for RTDN events, run:");
            Console.WriteLine("  PUBSUB_EMULATOR_HOST=localhost:8085 dotnet run listen");
        }
    }

    static void PrintBanner(string title)
    {
        var line = new string('=', 70);
        Console.WriteLine(line);
        Console.WriteLine(title);
        Console.WriteLine(line);
        Console.WriteLine();
    }

    /// <summary>
    /// Demonstrates basic API operations, orchestrated by per-step commands.
    /// </summary>
    static async Task RunApiDemo()
    {
        using var client = new HttpClient { BaseAddress = new Uri(EmulatorBaseUrl) };

        var ctx = new DemoContext
        {
            Client = client,
            PackageName = PackageName,
            SubscriptionId = SubscriptionId
        };

        var steps = new ICommand[]
        {
            new CreateSubscriptionCommand(),
            new QuerySubscriptionCommand("Query (initial)"),
            new AdvanceTimeCommand(366, "Advance time"),
            new QuerySubscriptionCommand("Query (after renewal)"),
            new PostCommand("Simulate payment failure", c => $"/emulator/subscriptions/{c.Token}/payment-failed"),
            new QuerySubscriptionCommand("Query (grace period)"),
            new PostCommand("Recover payment", c => $"/emulator/subscriptions/{c.Token}/payment-recovered"),
            new PostCommand("Cancel subscription", c => $"/emulator/subscriptions/{c.Token}/cancel", new { immediate = false }),
            new QuerySubscriptionCommand("Query (after cancel)")
        };

        foreach (var step in steps)
        {
            await step.ExecuteAsync(ctx);
            Console.WriteLine();
        }

        PrintBanner("API Demo completed!");
    }

    /// <summary>
    /// Demonstrates listening to Real-Time Developer Notifications via Pub/Sub.
    /// </summary>
    static async Task RunRtdnListenerDemo()
    {
        // Ensure the Pub/Sub client targets the emulator (no ADC needed)
        Environment.SetEnvironmentVariable("PUBSUB_EMULATOR_HOST", "localhost:8085");

        Console.WriteLine("Starting RTDN Event Listener...");
        Console.WriteLine($"Project: {PubSubProjectId}");
        Console.WriteLine($"Subscription: {PubSubSubscription}");
        Console.WriteLine();
        Console.WriteLine("Listening for events... (Press Ctrl+C to stop)");
        Console.WriteLine(new string('-', 70));
        Console.WriteLine();

        var subscriptionName = SubscriptionName.FromProjectSubscription(PubSubProjectId, PubSubSubscription);

        // Force emulator usage to avoid ADC lookups
        var subscriber = await new SubscriberClientBuilder
        {
            SubscriptionName = subscriptionName,
            EmulatorDetection = Google.Api.Gax.EmulatorDetection.EmulatorOnly
        }.BuildAsync();

        await subscriber.StartAsync((message, _) =>
        {
            try
            {
                var notification = JsonSerializer.Deserialize<DeveloperNotification>(message.Data.ToStringUtf8());
                var subNotif = notification?.SubscriptionNotification;
                if (subNotif != null)
                {
                    Console.WriteLine(new string('━', 70));
                    Console.WriteLine("RTDN Event Received");
                    Console.WriteLine(new string('━', 70));
                    Console.WriteLine($"Package: {notification!.PackageName}");
                    Console.WriteLine($"Event: {GetNotificationTypeName(subNotif.NotificationType)} ({subNotif.NotificationType})");
                    Console.WriteLine($"Subscription: {subNotif.SubscriptionId}");
                    Console.WriteLine($"Token: {subNotif.PurchaseToken}");
                    Console.WriteLine($"Time: {FormatTimestamp(notification.EventTimeMillis)}");
                    Console.WriteLine("✓ Acknowledged");
                    Console.WriteLine();
                }

                return Task.FromResult(SubscriberClient.Reply.Ack);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"✗ Error processing message: {ex.Message}");
                return Task.FromResult(SubscriberClient.Reply.Nack);
            }
        });

        var tcs = new TaskCompletionSource<bool>();
        Console.CancelKeyPress += (sender, e) =>
        {
            e.Cancel = true;
            tcs.TrySetResult(true);
        };

        await tcs.Task;
        await subscriber.StopAsync(CancellationToken.None);

        Console.WriteLine();
        Console.WriteLine("Listener stopped.");
    }

    internal static string FormatTimestamp(long milliseconds) =>
        milliseconds == 0 ? "N/A" : DateTimeOffset.FromUnixTimeMilliseconds(milliseconds).ToString("yyyy-MM-dd HH:mm:ss");

    internal static string GetPaymentStateName(int state) => state switch
    {
        0 => "PAYMENT_PENDING",
        1 => "PAYMENT_RECEIVED",
        2 => "FREE_TRIAL",
        3 => "PENDING_DEFERRED_UPGRADE_DOWNGRADE",
        _ => $"UNKNOWN_{state}"
    };

    static string GetNotificationTypeName(int type) => type switch
    {
        1 => "SUBSCRIPTION_RECOVERED",
        2 => "SUBSCRIPTION_RENEWED",
        3 => "SUBSCRIPTION_CANCELED",
        4 => "SUBSCRIPTION_PURCHASED",
        5 => "SUBSCRIPTION_ON_HOLD",
        6 => "SUBSCRIPTION_IN_GRACE_PERIOD",
        7 => "SUBSCRIPTION_RESTARTED",
        9 => "SUBSCRIPTION_DEFERRED",
        10 => "SUBSCRIPTION_PAUSED",
        12 => "SUBSCRIPTION_REVOKED",
        13 => "SUBSCRIPTION_EXPIRED",
        _ => $"UNKNOWN_{type}"
    };
}

// Command pattern scaffolding
interface ICommand
{
    Task ExecuteAsync(DemoContext ctx);
}

class DemoContext
{
    public HttpClient Client { get; init; } = default!;
    public string PackageName { get; init; } = "";
    public string SubscriptionId { get; init; } = "";
    public string Token { get; set; } = "";
    public string UserId { get; set; } = "";
    public JsonElement LastResponse { get; set; }
}

class CreateSubscriptionCommand : ICommand
{
    public async Task ExecuteAsync(DemoContext ctx)
    {
        Console.WriteLine("1) Creating a subscription...");
        ctx.UserId = $"dotnet-demo-{DateTimeOffset.UtcNow.ToUnixTimeMilliseconds()}";

        var resp = await ctx.Client.PostAsJsonAsync(
            "/emulator/subscriptions",
            new { package_name = ctx.PackageName, subscription_id = ctx.SubscriptionId, user_id = ctx.UserId });

        var parsed = await resp.Content.ReadFromJsonAsync<JsonElement?>();
        ctx.LastResponse = parsed.GetValueOrDefault();
        if (ctx.LastResponse.TryGetProperty("error", out _))
            throw new InvalidOperationException($"Create failed: {ctx.LastResponse.GetProperty("message").GetString()}");

        ctx.Token = ctx.LastResponse.GetProperty("token").GetString() ?? "";
        Console.WriteLine($"   ✓ Token: {ctx.Token}");
        Console.WriteLine($"   Order ID: {ctx.LastResponse.GetProperty("order_id").GetString()}");
        Console.WriteLine($"   Expiry: {Program.FormatTimestamp(ctx.LastResponse.GetProperty("expiry_time_millis").GetInt64())}");
    }
}

class QuerySubscriptionCommand : ICommand
{
    private readonly string _label;
    public QuerySubscriptionCommand(string label) => _label = label;

    public async Task ExecuteAsync(DemoContext ctx)
    {
        Console.WriteLine($"{_label}...");
        var resp = await ctx.Client.GetAsync(
            $"/androidpublisher/v3/applications/{ctx.PackageName}/purchases/subscriptions/{ctx.SubscriptionId}/tokens/{ctx.Token}");

        var parsed = await resp.Content.ReadFromJsonAsync<JsonElement?>();
        ctx.LastResponse = parsed.GetValueOrDefault();

        var priceMicros = long.Parse(ctx.LastResponse.GetProperty("priceAmountMicros").GetString() ?? "0");

        if (ctx.LastResponse.TryGetProperty("paymentState", out var paymentStateObj))
        {
            var paymentState = paymentStateObj.GetInt32();
            Console.WriteLine($"   Payment state: {Program.GetPaymentStateName(paymentState)} ({paymentState})");
            
        }
        
        Console.WriteLine($"   Auto-renewing: {ctx.LastResponse.GetProperty("autoRenewing").GetBoolean()}");
        Console.WriteLine($"   Price: ${priceMicros / 1_000_000.0:F2} {ctx.LastResponse.GetProperty("priceCurrencyCode").GetString()}");
        if (ctx.LastResponse.TryGetProperty("expiryTimeMillis", out var expiry))
        {
            Console.WriteLine($"   Expiry: {Program.FormatTimestamp(long.Parse(expiry.GetString() ?? "0"))}");
        }
    }
}

class AdvanceTimeCommand : ICommand
{
    private readonly int _days;
    private readonly string _label;
    public AdvanceTimeCommand(int days, string label)
    {
        _days = days;
        _label = label;
    }

    public async Task ExecuteAsync(DemoContext ctx)
    {
        Console.WriteLine($"{_label} by {_days} days...");
        await ctx.Client.PostAsJsonAsync("/emulator/time/advance", new { days = _days });
        Console.WriteLine("   ✓ Time advanced");
    }
}

class PostCommand : ICommand
{
    private readonly string _label;
    private readonly Func<DemoContext, string> _path;
    private readonly object? _body;

    public PostCommand(string label, Func<DemoContext, string> path, object? body = null)
    {
        _label = label;
        _path = path;
        _body = body;
    }

    public async Task ExecuteAsync(DemoContext ctx)
    {
        Console.WriteLine($"{_label}...");
        HttpResponseMessage resp = _body == null
            ? await ctx.Client.PostAsync(_path(ctx), null)
            : await ctx.Client.PostAsJsonAsync(_path(ctx), _body);

        var parsed = await resp.Content.ReadFromJsonAsync<JsonElement?>();
        ctx.LastResponse = parsed.GetValueOrDefault();
        Console.WriteLine("   ✓ Done");
    }
}

/// <summary>
/// Model for Google Play RTDN Developer Notification.
/// </summary>
public class DeveloperNotification
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("package_name")]
    public string PackageName { get; set; } = "";

    [JsonPropertyName("event_time_millis")]
    public long EventTimeMillis { get; set; }

    [JsonPropertyName("subscription_notification")]
    public SubscriptionNotification? SubscriptionNotification { get; set; }
}

/// <summary>
/// Model for subscription notification within RTDN.
/// </summary>
public class SubscriptionNotification
{
    [JsonPropertyName("version")]
    public string Version { get; set; } = "";

    [JsonPropertyName("notification_type")]
    public int NotificationType { get; set; }

    [JsonPropertyName("purchase_token")]
    public string PurchaseToken { get; set; } = "";

    [JsonPropertyName("subscription_id")]
    public string SubscriptionId { get; set; } = "";
}
