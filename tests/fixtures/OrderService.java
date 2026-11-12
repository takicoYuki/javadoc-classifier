package com.example.order;

import java.util.List;
import java.util.Map;

/**
 * 注文を管理するサービス。
 * <p>
 * 注文の登録・取消・検索を行う。{@link OrderRepository} を使って永続化する。
 *
 * @author Yuki Takita
 * @since 1.0
 */
public class OrderService {

    /** 1回の注文で登録できる明細の上限 */
    public static final int MAX_ITEMS = 100;

    private final OrderRepository repository;

    public static final String NO_DOC = "a;b{c}";

    private static final Map<String, Integer> PRICES = Map.of("a", 1);

    private final Runnable task = new Runnable() {
        @Override
        public void run() {
            System.out.println("not a member");
        }
    };

    /**
     * サービスを生成する。
     *
     * @param repository 注文の保存先
     */
    public OrderService(OrderRepository repository) {
        this.repository = repository;
    }

    /**
     * 注文を登録する。
     *
     * @param customerId 顧客ID
     * @param items      明細
     * @return 登録した注文の ID
     * @throws IllegalArgumentException 明細が空、または上限を超えるとき
     */
    public long register(String customerId, List<Item> items) throws IllegalArgumentException {
        if (items.isEmpty()) {
            return fail("empty");
        }
        return repository.save(customerId, items);
    }

    /**
     * 注文を取り消す。
     *
     * @param orderId 注文ID
     * @param reason  取消理由
     * @return 取り消せたら true
     */
    public void cancel(long orderId) throws OrderNotFoundException {
        repository.delete(orderId);
    }

    public List<Order> search(@Deprecated final Map<String, List<Integer>> conditions, String... keywords) {
        return List.of();
    }

    /**
     * @deprecated
     */
    @Deprecated
    public <T extends Order> T find(Class<T> type, long id) {
        return null;
    }

    @Override
    public String toString() {
        return "OrderService";
    }

    /**
     * 内部用。
     */
    private long fail(String message) {
        throw new IllegalArgumentException(message);
    }

    /** 注文の状態 */
    public enum Status {
        /** 受付済み */
        RECEIVED,
        CANCELLED;

        /** 終了状態か */
        public boolean isFinal() {
            return this == CANCELLED;
        }
    }

    /** 注文 */
    public record Order(long id, String customerId) {
    }

    public interface Listener {
        void onRegistered(long id);
    }
}
